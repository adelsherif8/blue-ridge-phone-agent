---
title: Voice agent latency, measured: where 1.74 seconds of reply time goes
seo_title: Voice agent latency: where the reply time goes
description: Voice agent latency measured stage by stage on 20 simulated calls: speech-to-text, LLM and voice, the slow tail, a measuring bug, and what to cut first.
date: 2026-11-05
slug: voice-agent-latency-breakdown
service: /voice-agent-engineer/
service_label: AI voice agent developer
tags: voice agent latency, pipecat, testing
target: voice agent latency
---
Voice agent latency is the gap between a caller going quiet and the agent starting to speak. On my phone agent it was 1.74 seconds at the median and 4.61 seconds at p95, over 20 simulated calls. At the median, the largest stage was the language model's first token, the moment it starts answering, at 0.87 seconds.

Is that fast enough? Most turns came in under two seconds, but one in 20 took 4.6 seconds or more, and those long pauses are what callers notice. I treat the median as workable and the tail as the problem to fix.

This post breaks that number into stages, shows one slow turn in detail, and explains a measuring bug that showed replies of almost two minutes. It ends with where I would cut time first.

## What exactly should you measure?

Measure from the moment the caller stops talking to the first byte of the agent's audio. That is what the caller feels. Measuring only the model's answer time, or only the voice, hides most of the wait.

I measured it twice:

- **On the server**, from the pipeline's own events: 1.74 s median, 4.61 s p95, over 55 turns.
- **On the simulated caller**, from its own clock: 1.80 s median, 4.63 s p95, over 69 turns.

The two agree within a tenth of a second. That gave me some trust in both.

## How does voice agent latency split into stages?

My agent runs on [Pipecat](https://docs.pipecat.ai/), an open-source pipeline, with Deepgram for speech-to-text and voice and OpenAI gpt-4.1-mini as the model. Here are the stage medians from the same calls:

| Stage | Median | p95 (19 in 20 turns at or under) |
|---|---|---|
| Speech-to-text, time to final transcript | 0.47 s | 0.72 s |
| Model, time to first token | 0.87 s | 1.15 s |
| Voice, time to first audio | 0.24 s | 0.44 s |

Separately, the greeting started 1.27 s (median) after the call connected.

The stage medians don't add up to the 1.74 s total. Medians usually don't add that way. There are also smaller steps in between: waiting to be sure the caller has finished, turn detection, and collecting the first sentence before the voice starts.

## What does one tool turn look like?

Here is a single turn from a burst-pipe call, as my call console shows it. It took 2.37 s in total, above the median but well below the p95. The transcription step here (0.24 s) is a narrower measure than the 0.47 s "time to final transcript" in the table, which also counts time while the caller is still speaking.

- Waiting for the caller to finish: 0.20 s
- Transcription: 0.24 s
- Turn detection: 0.02 s
- Model inference: 1.23 s
- Collecting the first sentence: 0.32 s
- Speech synthesis: 0.37 s

The model took more than half the turn. This was the turn where the agent decided to hand the call to a person, through the `transfer_to_human` tool. You can open the same waterfall for every turn in the [call console](/voice-agent-engineer/phone-agent/), built from the redacted test calls.

## Why does the slow tail matter more than the median?

A p95 of 4.61 s means about one turn in 20 took 4.6 seconds or more. Callers don't remember the median. They remember the long pause after they asked something important.

My guess is that tool calls drive much of the tail: when the model calls a tool, such as checking the schedule, the reply waits for the tool and for the model to read the result. I haven't split tool turns from the rest yet, so treat that as a lead, not a finding. The waterfall for each slow turn shows which stage stalled.

## The measuring bug that showed 112-second replies

My first summary showed outliers of 57 to 112 seconds. No caller waited that long.

The cause was in how I read the timing events. Turns that came right after a tool call were measured from the start of the call, not from the moment the caller stopped speaking. So they reported elapsed call time instead of reply time.

The fix was to keep only turns measured from the caller's silence. After that the numbers above made sense. The lesson: before you trust a latency number, check what it is measured from.

## What do these numbers leave out?

- **The phone network.** The calls were simulated: a script spoke Twilio's streaming protocol straight to my server. The network between a real caller and Twilio isn't in the number, so real calls will be somewhat slower.
- **Real callers.** The callers were a language model following personas. People mumble, talk over the agent and call from noisy rooms.
- **Load.** I didn't load-test it with many calls at once.

## Where would I cut time first?

These are the levers I would try, in order. I haven't measured their effect on this agent yet, so treat them as a plan, not results.

1. **The model's first token.** It's the largest stage. A shorter system prompt, a smaller or faster model, and fewer tool calls on routine turns all help here. OpenAI's [latency guide](https://platform.openai.com/docs/guides/latency-optimization) lists similar levers.
2. **Tool turns.** Say a short filler line while a slow tool runs, so the caller hears something. My agent already does this for checking the schedule.
3. **The first sentence.** Keep the first sentence of each reply short, so the voice can start sooner. Deepgram's [text-to-speech docs](https://developers.deepgram.com/docs/text-to-speech) cover streaming the audio as it's made.
4. **The end-of-speech wait.** A shorter wait answers faster but interrupts slow talkers more. Test it with real recordings before changing it.

## Is a hosted platform faster?

Not necessarily, and you may not be able to tell. With your own pipeline you see every stage, so you can find the slow one. Some hosted platforms show a per-stage breakdown and some show only a total, so check before you buy.

If that total is good enough for your callers, the platform is a fine choice. My [testing notes](/blog/how-we-test-ai-phone-agents/) show how I check agents on either route.

## A checklist for measuring your own agent

- Measure caller silence to first agent audio, not model time alone.
- Record each stage per turn: end-of-speech wait, transcription, model, first sentence, voice.
- Report p95 next to the median, and look at the slowest turns one by one.
- Check what each turn is measured from, especially after tool calls.
- Say what your test leaves out: phone network, real callers, load.

If you want this measured and tuned on your agent, start with the [voice agent developer page](/voice-agent-engineer/) and its [pricing](/pricing/).
