"""Pipecat voice pipeline for one phone call: Blue Ridge Plumbing receptionist."""

import asyncio
import os
import time
from datetime import datetime

from loguru import logger
from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    FunctionCallResultProperties,
    TTSSpeakFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import parse_telephony_websocket
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport
from pipecat.workers.runner import WorkerRunner

from app.crm import CRMSync, HubSpot
from app.facts import GREETING, SYSTEM_PROMPT, call_context
from app.schedule import TZ
from app.state import BOARD
from app.tools import FILLERS, NO_FILLER, TOOL_SPECS, Tools
from app.transfer import TransferAwareTwilioSerializer, redirect_call, transfer_twiml
from app.util import mask_phone


class SpeakingTracker(FrameProcessor):
    """Sits after the audio output and knows whether the bot is mid-sentence."""

    def __init__(self):
        super().__init__()
        self.speaking = False
        self.last_change = time.monotonic()

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, BotStartedSpeakingFrame):
            self.speaking, self.last_change = True, time.monotonic()
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self.speaking, self.last_change = False, time.monotonic()
        await self.push_frame(frame, direction)

    async def wait_until_quiet(self, settle: float = 0.6, timeout: float = 20.0):
        """Wait for any line already sent to TTS (e.g. the safety advice) to finish playing."""
        start = time.monotonic()
        await asyncio.sleep(settle)  # let TTS start on text the LLM produced just before the tool call
        while time.monotonic() - start < timeout:
            if not self.speaking and time.monotonic() - self.last_change >= settle:
                return
            await asyncio.sleep(0.1)


async def run_bot(transport, serializer, websocket, runner_args: RunnerArguments, call_sid: str,
                  caller_id: str | None):
    crm = CRMSync(HubSpot(os.environ["HUBSPOT_TOKEN"]) if os.getenv("HUBSPOT_TOKEN") else None)
    tracker = SpeakingTracker()
    background: list[asyncio.Task] = []
    transfer_to = os.getenv("TRANSFER_NUMBER")

    def on_transfer(reason: str, summary: str):
        serializer.transferred = True  # from now on Pipecat must not hang up this call

        async def go():
            await tracker.wait_until_quiet()
            twiml = transfer_twiml(public_url=os.environ["PUBLIC_URL"], to_number=transfer_to,
                                   from_number=os.environ["TWILIO_PHONE_NUMBER"], reason=reason,
                                   summary=summary, caller_id=caller_id)
            try:
                await redirect_call(call_sid, twiml)
            except Exception as e:
                logger.error(f"Transfer redirect failed: {e}")
                serializer.transferred = False
                return
            if os.getenv("TRANSFER_DRY_RUN") == "1":
                await websocket.close()  # what Twilio does when the new TwiML replaces <Connect>

        background.append(asyncio.create_task(go()))

    tools = Tools(BOARD, caller_id, on_job=crm.submit, on_transfer=on_transfer if transfer_to else None)
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
        result = tools.run(params.function_name, dict(params.arguments or {}))
        quiet = result.get("status") == "Transferring"  # the hold line is Twilio's; Sam says nothing more
        await params.result_callback(result, properties=FunctionCallResultProperties(run_llm=not quiet))

    schemas = [FunctionSchema(name=s["name"], description=s["description"], properties=s["properties"],
                              required=s["required"], handler=handle) for s in TOOL_SPECS]

    last_filler = [0.0]

    @llm.event_handler("on_function_calls_started")
    async def on_tools(service, function_calls):
        # At most one filler per caller turn: chained tool calls inside one turn stay quiet.
        name = function_calls[0].function_name if function_calls else ""
        filler = FILLERS.get(name)
        if filler and name not in NO_FILLER and time.monotonic() - last_filler[0] > 8:
            last_filler[0] = time.monotonic()
            await service.push_frame(TTSSpeakFrame(filler, append_to_context=False))

    context = LLMContext(
        messages=[{"role": "developer", "content": call_context(datetime.now(TZ), caller_id)}],
        tools=ToolsSchema(standard_tools=schemas),
    )
    user_agg, assistant_agg = LLMContextAggregatorPair(
        context, user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer())
    )

    pipeline = Pipeline([transport.input(), stt, user_agg, llm, tts, transport.output(), tracker, assistant_agg])
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
        logger.info("Transferred: bot left the call" if serializer.transferred else "Caller hung up")
        for m in context.get_messages():
            if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str):
                logger.info(f"TRANSCRIPT {m['role']}: {m['content']}")
        await runner.cancel()

    await runner.run()
    if background:
        await asyncio.gather(*background, return_exceptions=True)
    for r in await crm.drain():
        logger.info(f"CRM result: {r}")
    if crm.crm:
        await crm.crm.aclose()


async def bot(runner_args):
    """Entry point from /ws: build the Twilio transport ourselves so we control hang-up."""
    websocket = runner_args.websocket
    _, call_data = await parse_telephony_websocket(websocket)  # cached; already read by the server
    body = call_data.get("body") or {}
    serializer = TransferAwareTwilioSerializer(
        stream_sid=call_data["stream_id"],
        call_sid=call_data["call_id"],
        account_sid=os.environ["TWILIO_ACCOUNT_SID"],
        auth_token=os.environ["TWILIO_AUTH_TOKEN"],
    )
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(audio_in_enabled=True, audio_out_enabled=True, add_wav_header=False,
                                      serializer=serializer),
    )
    await run_bot(transport, serializer, websocket, runner_args, call_data["call_id"], body.get("caller") or None)
