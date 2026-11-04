"""Pipecat voice pipeline for one phone call: Blue Ridge Plumbing receptionist."""

import os
from datetime import datetime

from loguru import logger
from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams
from pipecat.workers.runner import WorkerRunner

from app.facts import GREETING, SYSTEM_PROMPT, call_context
from app.schedule import TZ, Board
from app.tools import FILLERS, TOOL_SPECS, Tools
from app.util import mask_phone

# One board per server process, shared by all calls (a real deployment would use a database).
BOARD = Board()


async def run_bot(transport, runner_args: RunnerArguments, caller_id: str | None):
    tools = Tools(BOARD, caller_id)
    logger.info(f"Call started, caller {mask_phone(caller_id)}")

    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])
    llm = OpenAILLMService(
        api_key=os.environ["OPENAI_API_KEY"],
        settings=OpenAILLMService.Settings(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            system_instruction=SYSTEM_PROMPT,
            temperature=0.3,
        ),
    )
    tts = DeepgramTTSService(
        api_key=os.environ["DEEPGRAM_API_KEY"],
        settings=DeepgramTTSService.Settings(voice=os.getenv("DEEPGRAM_TTS_VOICE", "aura-2-thalia-en")),
    )

    async def handle(params: FunctionCallParams):
        await params.result_callback(tools.run(params.function_name, dict(params.arguments or {})))

    schemas = [FunctionSchema(name=s["name"], description=s["description"], properties=s["properties"],
                              required=s["required"], handler=handle) for s in TOOL_SPECS]

    @llm.event_handler("on_function_calls_started")
    async def on_tools(service, function_calls):
        filler = FILLERS.get(function_calls[0].function_name) if function_calls else None
        if filler:
            await service.push_frame(TTSSpeakFrame(filler, append_to_context=False))

    context = LLMContext(
        messages=[{"role": "developer", "content": call_context(datetime.now(TZ), caller_id)}],
        tools=ToolsSchema(standard_tools=schemas),
    )
    user_agg, assistant_agg = LLMContextAggregatorPair(
        context, user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer())
    )

    pipeline = Pipeline([transport.input(), stt, user_agg, llm, tts, transport.output(), assistant_agg])
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(audio_in_sample_rate=8000, audio_out_sample_rate=8000,
                              enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )
    runner = WorkerRunner(handle_sigint=False, force_gc=True)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_connected(transport, client):
        # Fixed greeting: no LLM round trip before the caller hears us. Also appended to context.
        await worker.queue_frames([TTSSpeakFrame(GREETING)])

    @transport.event_handler("on_client_disconnected")
    async def on_disconnected(transport, client):
        logger.info("Caller hung up")
        for m in context.get_messages():
            if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str):
                logger.info(f"TRANSCRIPT {m['role']}: {m['content']}")
        await runner.cancel()

    await runner.run()


async def bot(runner_args: RunnerArguments):
    transport = await create_transport(
        runner_args,
        {"twilio": lambda: FastAPIWebsocketParams(audio_in_enabled=True, audio_out_enabled=True)},
    )
    body = (runner_args.call_data.get("body") or {}) if runner_args.call_data else {}
    await run_bot(transport, runner_args, body.get("caller") or None)
