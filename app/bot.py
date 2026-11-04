"""Pipecat voice pipeline for one phone call (Milestone 1: greet and chat)."""

import os

from loguru import logger
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
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams
from pipecat.workers.runner import WorkerRunner

SYSTEM_PROMPT = """You are the phone receptionist for Blue Ridge Plumbing.
You are on a live phone call, so everything you write is spoken aloud.
Reply in one or two short sentences, at most 35 words. Ask one question per turn.
No lists, no markdown, no symbols, never read out URLs.
If you do not know something, say so and offer a callback. Never invent prices or times."""

GREETING = "Thanks for calling Blue Ridge Plumbing, this is Riley. How can I help you today?"


async def run_bot(transport, runner_args: RunnerArguments):
    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])
    llm = OpenAILLMService(
        api_key=os.environ["OPENAI_API_KEY"],
        settings=OpenAILLMService.Settings(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            system_instruction=SYSTEM_PROMPT,
        ),
    )
    tts = DeepgramTTSService(
        api_key=os.environ["DEEPGRAM_API_KEY"],
        settings=DeepgramTTSService.Settings(voice=os.getenv("DEEPGRAM_TTS_VOICE", "aura-2-thalia-en")),
    )

    context = LLMContext()
    user_agg, assistant_agg = LLMContextAggregatorPair(
        context, user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer())
    )

    pipeline = Pipeline(
        [transport.input(), stt, user_agg, llm, tts, transport.output(), assistant_agg]
    )
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )
    runner = WorkerRunner(handle_sigint=False, force_gc=True)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_connected(transport, client):
        # Fixed greeting: no LLM round trip before the caller hears us.
        # TTSSpeakFrame also appends it to the LLM context.
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
    await run_bot(transport, runner_args)
