# LinkedIn kit: Blue Ridge phone agent

Written 2026-11-05. Adel posts everything himself. No links in post bodies (they cut reach); the link goes in the
first comment. Every number is a measured one from the README; keep the limits in the text when you edit.

## Profile: Featured
1. Feature **Post 1** (the native video) once it is live: on the post, `...` > Feature on top of profile.
2. Add a link: Featured > + > Add a link > `https://adelatya.com/voice-agent-engineer/phone-agent/`
   - Title (43): AI phone receptionist on my own voice stack
   - Description (123): Pipecat on Twilio with HubSpot sync and live transfer. Call console from 20 simulated calls, every turn timed and redacted.
   - Image: `~/Desktop/GHAI/phone-agent/docs/ship/thumb/cover.png`

## Profile: Projects
- Name (69): Blue Ridge phone agent: AI receptionist on an open-source voice stack
- Dates: Nov 2026 (set the start month to when you began Milestone 1)
- Associated with: your independent / freelance position
- Skills (5): Python (Programming Language) · Twilio · Large Language Models (LLM) · HubSpot · FastAPI
- Media: `docs/ship/thumb/cover.png`, `docs/ship/shots/2-live-call.png` … `5-console.png`, link `https://adelatya.com/voice-agent-engineer/phone-agent/`
- Description (1066 of 2,000):

An AI receptionist for a demo plumbing company on a real Twilio number, built on my own real-time pipeline (Pipecat) instead of a rented platform like Vapi or Retell.

What it does:
- Answers over Twilio Media Streams: Deepgram speech-to-text, GPT-4.1 mini, Deepgram Aura-2 voice
- Checks a live schedule before booking, offers open windows, reads the address back, books or reschedules
- Writes each booking to HubSpot as a contact plus a linked meeting, in the background
- Live hand-off on request, in an emergency or when stuck: one hold line, then Twilio transfers the call; the person who answers hears a spoken summary first
- Guardrails in code, PII redacted before saving, Twilio signatures verified
- Every call logged with per-turn latency and shown in a call console

Measured over 20 simulated calls: median reply 1.74 s, p95 4.61 s. Text evals 56, 56 and 57 of 57 over 19 scenarios; 98 unit tests in CI.

Limits: calls were simulated over Twilio's streaming protocol (no phone network in the latency), transfers tested in dry-run mode, not hosted 24/7.

## Posting order
One post every 2 to 3 days, weekday mornings in US Eastern time (most buyers are in the US).
Reply to every comment in the first hour. Post 1 first so it can be featured.

## Post 1 · Own stack vs rented
- Format: Native video (16:9, 59.8 s)
- Asset: `~/Desktop/GHAI/phone-agent/docs/video/out/phone-agent.mp4`
- Audience: Technical buyers: SaaS and voice teams, CTOs (the own-stack line is allowed here)
- Length: 1106 characters (hook 56, shown before "see more")

```
I built an AI phone receptionist without Vapi or Retell.

It does the same job those platforms do: answers a real Twilio number, books jobs, syncs the CRM, hands the call to a person. The difference is that every piece is code I own:
- Twilio streams the call audio to my server over a WebSocket
- Pipecat runs the pipeline: Deepgram hears, GPT-4.1 mini decides, Aura-2 speaks
- Tools check a live schedule, book, reschedule, save callbacks and transfer
- Every booking lands in HubSpot as a contact plus a linked meeting

Why bother? No per-minute platform markup, and no lock-in: switching the voice is a one-line change. I can also time every stage of every turn instead of guessing.

Measured over 20 simulated calls: 1.74 s median from the caller going quiet to the bot speaking, 4.61 s p95. 98 unit tests in CI.

What isn't proven yet: these were simulated calls over Twilio's streaming protocol, not dialed from a phone, so the phone network isn't in the number. Transfers ran in dry-run mode.

Your own voice stack, not a rented one. The 60-second walkthrough is above.

#VoiceAI #Pipecat #AIAgents
```

First comment:
```
The call console with the redacted test calls, every turn timed: adelatya.com/voice-agent-engineer/phone-agent/
```

## Post 2 · Latency
- Format: Document carousel (PDF, 7 pages)
- Asset: `carousel-latency.pdf`
- Audience: Technical buyers
- Length: 641 characters (hook 109, shown before "see more")

```
1.74 seconds. That's the median time my AI phone agent takes to start answering after a caller stops talking.

One number hides where the time goes, so I broke it down by stage (medians):
- Speech-to-text final transcript: 0.47 s
- LLM first token: 0.87 s
- Voice first audio: 0.24 s

The slow tail matters more than the median. p95 is 4.61 s, so 1 turn in 20 takes 4.6 s or more. Those are the turns callers remember.

The limits are in the deck too: 20 simulated calls over Twilio's streaming protocol, no phone network in the number, LLM callers instead of people.

Swipe through for where every second goes.

#VoiceAI #LLM #AIEngineering
```

First comment:
```
Every turn's timing waterfall, in the call console: adelatya.com/voice-agent-engineer/phone-agent/
```

## Post 3 · Live hand-off
- Format: Native vertical video (1080x1920, 14.4 s)
- Asset: `vertical-handoff-15s.mp4`
- Audience: Home-services owners and agencies (no own-stack line)
- Length: 712 characters (hook 60, shown before "see more")

```
2 AM. A pipe bursts in the basement. Who answers your phone?

Here's what my AI receptionist does on that call:
1. Safety first: "If you can reach it safely, shut off the main water valve now."
2. One hold line, then the call rings your on-call technician.
3. Before the caller is put through, the technician hears a short summary: emergency, burst pipe, basement.
4. The AI leaves the call. Caller and technician are talking, and nobody repeats the story.

If nobody picks up, the caller is offered a callback and it is saved.

This is a simulated call, re-voiced for the video, and the transfer was tested in dry-run mode.

Would your after-hours line handle this call?

#HomeServices #Plumbing #AIReceptionist
```

First comment:
```
The same call, with the transfer reason and summary, in the call console: adelatya.com/voice-agent-engineer/phone-agent/
```

## Post 4 · Guardrails / never makes things up
- Format: Document carousel (PDF, 7 pages)
- Asset: `carousel-guardrails.pdf`
- Audience: Owners, agencies and technical buyers (no own-stack line)
- Length: 801 characters (hook 118, shown before "see more")

```
The worst thing an AI receptionist can do is make something up. A price, a free visit, a time slot that doesn't exist.

So the rules on my phone agent live in code, not just in the prompt:
1. No booking before checking the real schedule
2. One booking per call, never someone else's job
3. No transfer without a reason, and safety advice first in an emergency
4. Prices and facts only from the business's own fact card; anything else becomes a saved callback
5. Caller tricks (a fake owner's discount, "ignore your instructions") don't change any of it

In test calls the model sometimes tried to book before checking the schedule. The code refused every time.

19 test scenarios, last three runs: 56, 56 and 57 of 57. 98 unit tests in CI.

Swipe for the five rules.

#AIAgents #VoiceAI #SmallBusiness
```

First comment:
```
The refused bookings are visible call by call in the console: adelatya.com/voice-agent-engineer/phone-agent/
```

## Post 5 · Privacy + call console
- Format: Image post (2000x1500)
- Asset: `~/Desktop/GHAI/phone-agent/docs/ship/shots/5-console.png`
- Audience: Ops leads, call centres, agencies (no own-stack line)
- Length: 790 characters (hook 87, shown before "see more")

```
Every call my AI phone agent takes is saved, timed and redacted before anyone reads it.

Per call, the console shows:
- the transcript, with each tool call in place (check schedule, book, transfer)
- names, phone numbers and addresses replaced by chips, including addresses spoken as words
- the hand-off reason and the summary the technician heard
- a timing waterfall for every turn: speech-to-text, LLM, voice

Logs keep only the last four digits of a phone number, and every Twilio webhook is signature-checked.

One limit I'm open about: redaction is pattern-based. It catches numbers, addresses and the names callers give, but a name mentioned some other way can slip through.

If you run a call team: what do you check first when a call goes wrong?

#VoiceAI #DataPrivacy #CallCenter
```

First comment:
```
Open the console yourself (test calls, all redacted): adelatya.com/voice-agent-engineer/phone-agent/
```

## Assets in this folder
- `carousel-latency.pdf`, `carousel-guardrails.pdf`: upload as a Document; set the document title to the first slide's headline.
- `vertical-handoff-15s.mp4`: 1080x1920, 14.4 s, built by `make_vertical.py` from `build.py --nocap`.
- Rebuild everything: `build.py --nocap`, then `make_vertical.py` and `make_carousels.py` (voicedesk .venv python).
- After Step 7, if the repo is public, add `github.com/adelsherif8/blue-ridge-phone-agent` to the first comments.
