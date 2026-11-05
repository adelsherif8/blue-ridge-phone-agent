---
title: How a Pipecat Twilio phone agent fits together, from ring to booking
seo_title: Pipecat Twilio phone agent: how the pieces fit
description: How a Pipecat Twilio phone agent works: the call audio path, tools, CRM sync and live transfer, with the reply times I measured and what I'd skip.
date: 2026-11-05
slug: pipecat-twilio-phone-agent
service: /voice-agent-engineer/
service_label: AI voice agent developer
tags: pipecat, twilio, voice agents
target: pipecat twilio phone agent
---
A Pipecat Twilio phone agent is three parts. Twilio answers the number and streams the call audio to your server. Pipecat runs speech-to-text, the language model and the voice as one pipeline. Your own code handles tools like booking and transfer, so you can change any vendor and time every step.

I built one for a demo plumbing company and measured it. This post follows one call from ring to booking. It also says when a hosted platform is the better choice.

## What happens when the phone rings?

Twilio gets the call first and sends a webhook to your server. Your server answers with a short instruction: connect this call to my WebSocket. From then on, Twilio's [Media Streams](https://www.twilio.com/docs/voice/media-streams) sends the caller's audio in small chunks. It plays back whatever audio you send.

Two security steps belong here, before any audio flows:

- Check the [Twilio request signature](https://www.twilio.com/docs/usage/webhooks/webhooks-security) on every webhook, so nobody else can start calls on your server.
- Put a one-time token in the connect instruction. The media endpoint then accepts only the call you just answered.

## What does Pipecat do in the middle?

[Pipecat](https://github.com/pipecat-ai/pipecat) is an open-source Python framework for real-time voice, under the BSD 2-Clause license. It moves audio and text through a chain of processors. In my build the chain is:

1. **Speech-to-text.** Deepgram turns the caller's audio into text as they speak.
2. **Turn detection.** The pipeline decides the caller has finished, so the bot doesn't talk over them.
3. **Language model.** OpenAI gpt-4.1-mini reads the conversation and either answers or calls a tool.
4. **Voice.** Deepgram Aura-2 speaks the reply. The pipeline hands it the first full sentence instead of waiting for the whole reply, which shows up as a "sentence aggregation" step in each turn's timing.
5. **Back to Twilio.** The audio goes back down the same WebSocket to the caller.

Each stage is a separate processor, so swapping one is a small change. Switching the voice to another provider is one line in my bot file.

## What does one booking call sound like?

Here is the routine booking from my tests, condensed and re-voiced for the demo video: the filler lines and the step where it asks the caller's first name are cut. Tool calls are marked.

- **Caller:** Hi Sam, my bathroom faucet is dripping constantly. Can someone come tomorrow afternoon?
- *Tool:* `check_slots(tomorrow)` returns the open windows
- **Agent:** Tomorrow afternoon we have two to four PM and four to six PM. Which works best?
- **Caller:** Two to four, please. I'm at 41 Laurel Drive.
- **Agent:** That's forty-one Laurel Drive, right?
- **Caller:** Yes.
- *Tool:* `book_job(name, address, problem, day, window, urgency)` returns Booked
- **Agent:** Your visit is booked for tomorrow, two to four PM, with an eighty-nine dollar call-out fee.

The agent offers at most two windows, reads the address back, and only says "booked" after the tool confirms it.

## Where do bookings and transfers live?

Not in the prompt. The model can call five tools: `check_slots`, `book_job`, `change_booking`, `request_callback` and `transfer_to_human`. Each one is plain Python with its own rules:

- `book_job` refuses to run until `check_slots` has run for that day.
- A second booking on the same call is refused; a change moves the caller's own booking.
- `transfer_to_human` needs a reason and a summary.

These rules matter. In my test calls the model sometimes tried to book before checking the schedule. The code refused every time, and the model then checked the schedule as it should. A rule that lives only in the prompt can't promise that.

Each booking also goes to HubSpot. The code finds or creates the contact by phone number, then adds a linked [meeting](https://developers.hubspot.com/docs/api/crm/meetings). This runs in the background, so the caller never waits on the CRM. Unit tests cover the HubSpot client against a fake API.

## How does a live transfer work without hanging up?

When the caller asks for a person, reports an emergency or a gas smell (after the safety advice), or the agent is stuck after two tries, the model calls `transfer_to_human` and goes quiet. The server then uses Twilio's [call update API](https://www.twilio.com/docs/voice/api/call-resource) to give the live call new instructions. Twilio says one hold line, then [dials](https://www.twilio.com/docs/voice/twiml/dial) the on-call number.

The person who answers hears a spoken summary first. The caller doesn't repeat the story.

One detail took real work. When the bot leaves, the WebSocket closes, and by default that can end the call.

The fix: the pipeline's Twilio serializer skips the hang-up after a transfer. I tested this path with unit tests and simulated calls in dry-run mode. No live call was bridged to a phone.

## How fast is it?

I ran 20 simulated calls across 19 scenarios. A script spoke Twilio's Media Streams protocol to the real server. A language model played the caller.

| Measured on the server | Median | p95 |
|---|---|---|
| Caller stops talking to bot audio | 1.74 s | 4.61 s |
| Speech-to-text final transcript | 0.47 s | 0.72 s |
| Language model first token | 0.87 s | 1.15 s |
| Voice first audio | 0.24 s | 0.44 s |

p95 means 19 turns in 20 were at or under that. First token is the moment the model starts its answer.

These numbers leave out the phone network between the caller and Twilio. Real calls will be somewhat slower. The biggest single stage is the model's first token.

You can see every turn's timing for yourself in the [call console](/voice-agent-engineer/phone-agent/), built from the redacted test calls.

## What does the voice cost per call?

The agent spoke about 460 characters per call on average, across 19 test calls. At Deepgram Aura-2's [list price](https://deepgram.com/pricing) on 2026-11-05, $0.030 per 1,000 characters, that's about $0.014 per call for the voice. I only measured the voice cost. Speech-to-text, the model's tokens and Twilio minutes are billed on top.

## When is a Pipecat Twilio phone agent the wrong choice?

A hosted platform like Vapi or Retell is the better choice when:

- You need a working pilot this week and nobody on your side will maintain Python code.
- Your call volume is low, so a per-minute platform fee costs less than an engineer's time.
- You don't need to see inside each turn or change vendors.

Pipecat makes sense when you want to own the code and skip a per-minute platform markup. It also fits when you want to swap vendors or tune each stage. My [notes on hiring a Vapi or Retell developer](/blog/hire-vapi-retell-developer/) cover the platform side.

## What did the tests catch?

On the first voice run, 12 of 20 calls passed. Six failures were bugs in my test harness, now fixed. One was a network drop.

One was real: speech-to-text heard "Tom" as "Tong", so the transfer summary carried the wrong name. The text-only evals use rule checks and a GPT-4.1 judge. They passed 56, 56 and 57 of 57 on the last three runs. More in [how I test AI phone agents](/blog/how-we-test-ai-phone-agents/).

## A checklist before you build one

- Get a Twilio number and confirm the account can receive calls from any caller, not only verified ones.
- Write down the tools the agent needs and the rule each one must enforce in code.
- Decide where bookings go (calendar, CRM) and make that write run in the background.
- Plan the transfer: the on-call number, the hold line, the summary, and what happens if nobody answers.
- Check webhook signatures and redact names, numbers and addresses before saving any call.
- Measure reply time per stage on simulated calls before the first real caller.

If you want this built on your own number, start with the [voice agent developer page](/voice-agent-engineer/) and its [pricing](/pricing/).
