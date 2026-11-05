---
title: AI receptionist live transfer: how the hand-off to a person should work
seo_title: AI receptionist live transfer: how a good hand-off works
description: How an AI receptionist live transfer should work: when to hand off, the hold line, a spoken summary for your tech, and what happens if nobody answers.
date: 2026-11-05
slug: ai-receptionist-live-transfer
service: /plumbing/
service_label: AI phone agent for plumbing and HVAC
tags: ai receptionist, live transfer, home services
target: ai receptionist live transfer
---
A good AI receptionist live transfer puts the caller through to a person without making them repeat anything. The agent says one short hold line, rings your on-call phone, and the person who answers hears a spoken summary before the caller is connected. If nobody answers, the caller is told the office will call back, and the request is saved.

I built this into a phone agent for a demo plumbing company. Below is how each step works, the rules behind it, and exactly what I have and haven't tested.

## When should an AI receptionist transfer the call?

Only with a reason. My agent has four, and the code rejects a transfer without one of them and a summary:

- **Caller request.** The caller asks for a person, the owner or a manager. The agent asks once: "I can connect you now, or have the office call you back. Which would you like?" If they already said "put me through", it transfers right away.
- **Emergency.** A burst pipe, flooding, sewage backing up, or no water at all.
- **Safety.** A gas smell, or anyone hurt or in danger.
- **Stuck.** The agent can't help after two tries, or the caller is upset and repeating themselves.

The agent never chooses the callback for the caller. That choice stays with them.

## What should an AI receptionist live transfer sound like to the caller?

One hold line, then ringing: "Connecting you to our on-call team now. Please stay on the line."

Long hold scripts make a stressed caller more stressed. Under the hood, the agent tells Twilio to change the live call: [say](https://www.twilio.com/docs/voice/twiml/say) the hold line, then [dial](https://www.twilio.com/docs/voice/twiml/dial) your on-call number. My build rings for 25 seconds before it falls back.

## What does the person who answers hear?

A spoken summary, before the caller is put through. On the burst-pipe test call it ended: "...Emergency. Caller has a burst pipe spraying water in the basement."

This is what makes it a warm hand-off. A cold transfer drops the caller on your technician, who has to ask them to start again. With the summary, your technician answers knowing what's going on.

After the summary, the AI leaves. Unit tests and simulated calls check that the bot leaving doesn't hang up the call; I haven't yet bridged a live call to a phone.

## What should the summary contain?

One sentence, built from what the caller actually said:

1. **The reason.** The system says it first: emergency, safety, caller request, or the agent could not help.
2. **The problem.** "Burst pipe spraying water", not "plumbing issue".
3. **Where.** The address, if the caller gave it.
4. **Who.** A first name, only if the caller said their own name.

Leave out anything the agent guessed.

Names are the weak spot. In my tests, speech-to-text heard "Tom" as "Tong", and the wrong name went into the summary. The agent reads addresses back to the caller, but not names. If names matter to you, add a name read-back before the transfer.

## How should emergencies be handled before the transfer?

Safety advice comes first, then the transfer. My agent doesn't book emergencies at all. It gives the safety line and hands the call to a person.

- **Burst pipe, flooding, sewage or no water:** its first sentence is "If you can reach it safely, shut off the main water valve now." Then the transfer.
- **Gas smell:** leave the house now, don't switch anything on or off, and call the gas company or 911 from outside. Then the transfer. This matches utility guidance such as the [Connecticut regulator's page](https://portal.ct.gov/pura/gas-pipeline-safety/what-to-do-if--you-smell-natural-gas), which says to leave the building first if the smell is strong.

Your own wording should come from your business and your local gas company. The agent should read it, not improvise it.

## What if nobody answers?

The caller should never hit a dead end. In my build, if the technician doesn't pick up, Twilio plays a short message: the request is saved and the office will call back, and anyone in danger should hang up and call 911. The callback request is saved with the reason and summary.

Decide this before go-live:

- Who is on call, and on which number, by hour and day.
- How long it rings before the fallback. I used 25 seconds; pick what your team can meet.
- Where the callback request lands, so a person sees it first thing.

A transferred call also keeps using phone minutes while it rings and while your technician talks, so check your [Twilio voice pricing](https://www.twilio.com/en-us/voice/pricing) for both legs of the call.

## What have I actually tested?

Honest status for my build, which runs on the open-source [Pipecat](https://github.com/pipecat-ai/pipecat) voice pipeline:

- **Simulated calls, not real ones.** A script spoke Twilio's streaming protocol to my server, and a language model played each caller. No test used a real phone call.
- **Transfers in dry-run mode.** The agent made the transfer decision and built the Twilio instructions, including the no-answer fallback, but no live call was ever bridged to a phone.
- **The numbers.** In a 20-call voice test, 12 passed on the first run. Of the 8 failures, 6 were bugs in my test setup (now fixed), 1 was a network drop, and 1 was the misheard name. The transfer instructions are also covered by unit tests, part of 98 that run on every push.
- **Booking guardrail.** In some calls the model tried to book before checking the schedule. The code refused every time.

You can see the hand-off reason and summary on each transferred test call in the [call console](/voice-agent-engineer/phone-agent/), with names and addresses redacted.

## Is a live transfer better than an answering service?

It depends on your calls. If most after-hours calls are emergencies that need a technician, a fast warm hand-off matters most. If most are routine bookings, an AI that books on the spot saves more time than any transfer. I compare the two in [AI receptionist vs answering service](/blog/ai-receptionist-vs-answering-service/).

## When is a live transfer not worth setting up?

When nobody can pick up. If you have no on-call person after hours, a transfer only adds ringing. Then set the agent to take a detailed callback request instead. The [plumbing and HVAC page](/plumbing/) shows how that fits a trade business.

## A checklist before you turn it on

- Write the transfer reasons as rules the code enforces, not only the prompt.
- Write the hold line in one sentence.
- Write the summary rule: reason, problem, address, and a name only if the caller gave it.
- Get the emergency safety lines from your own process and your gas company.
- Set the on-call schedule, the ring time, and where the fallback callback lands.
- Before launch, call from a real phone, trigger each reason, and listen to what your technician hears.

For setup and costs, see [pricing](/pricing/).
