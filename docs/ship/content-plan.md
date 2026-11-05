# Content plan: one idea per feature (Blue Ridge phone agent)

For posts and videos made in another chat. Every number is a measured one from the README; keep the limit next to it.
Segments: **T** technical buyers (SaaS and voice teams, CTOs), **O** home-services owners, **A** agencies reselling
voice, **C** call-centre and ops leads. The line "Your own voice stack, not a rented one" is for **T** pieces only.
Formats: carousel = PDF document post; reel = vertical 9:16 video (LinkedIn, Instagram); short = 15-30 s clip;
text = text post with one image. Links go in the first comment, never in the post body.

| # | Feature | Segment | Hook (first line) | Format | CTA |
|---|---|---|---|---|---|
| 1 | Answers in under two seconds (1.74 s median, simulated) | O, T | "A caller decides in the first pause whether they're talking to a machine." | short: split screen, caller line then reply with the stopwatch from the video | "What does your phone do on ring four?" |
| 2 | Books on the live schedule, max two windows, no double-booking | O | "'We'll call you back to schedule' is where jobs go to die." | reel: the schedule board filling in from the video (call 1) | "Comment SCHEDULE and I'll show you how it hooks into yours." |
| 3 | Reads details back (address, fee from the fact card) | O | "Forty-one Laurel Drive or forty Laurel Drive? One digit, one wasted truck roll." | short: the read-back exchange with the address highlighted | "Ask me what else it confirms before booking." |
| 4 | Never makes things up (facts only from the business, unknowns become a callback) | O, A | "The worst thing an AI receptionist can do is quote a price you never set." | text + image (guardrails slide 5) | "What would you never want an AI to promise your customers?" |
| 5 | HubSpot sync with no data entry (contact + linked meeting, in the background) | A, O | "Your office manager shouldn't retype a phone call into the CRM." | carousel: call, then contact, then meeting, then reschedule moving the meeting | "Which CRM are you on? HubSpot, GHL, something else?" |
| 6 | Live hand-off with a spoken summary (dry-run tested) | O, A | "Nobody should have to tell their emergency twice." | reel: the 15 s vertical cut | "Who picks up your 2 AM calls today?" |
| 7 | Emergency triage (gas: get out first; burst pipe: shut-off valve first) | O | "At 2 AM, the first thing a caller needs is not a booking." | short: gas-smell scenario, script on screen, then transfer | "Save this for your after-hours checklist." |
| 8 | Callbacks that are actually saved | O | "'I'll pass that on' is a promise most phone systems can't keep." | text + console screenshot of a callback call | "How many 'call me back' messages did you lose last month?" |
| 9 | Guardrails in code, not just the prompt (refused early bookings, injection and fake-discount callers in tests) | T, A | "The prompt says don't. The code makes sure." | carousel (`carousel-guardrails.pdf`) | "What rule would you put in code first?" |
| 10 | Honest about being AI | O, C | "My phone agent tells callers it's a virtual assistant. Here's why that helps." | text post with the greeting line as a quote card | "Would you tell your callers? Yes or no in the comments." |
| 11 | Privacy by default (redaction before saving, last four digits only, signed webhooks; regex limits disclosed) | C, A | "Every call is redacted before anyone reads it, including addresses spoken as words." | carousel: a raw line vs the redacted line, then the limits slide | "Ask me for the redaction checklist." |
| 12 | Every call measured and graded (per-turn latency, 19 scenarios, LLM judge + rules) | C, T | "Your call center has QA. Your AI receptionist should too." | carousel (`carousel-latency.pdf`) or a screen recording of the console | "Open the console yourself: link in the comments." |
| 13 | You own the stack (open-source pipeline, no per-minute platform markup) | T | "I built a phone agent without Vapi or Retell. Here's what that buys you." | native video (the 60 s walkthrough) | "Your own voice stack, not a rented one. DM me 'stack'." |

## Video ideas beyond the posts
- 45 s "how the call flows" explainer: the pipeline X-ray from the video, narrated, one stage per beat (T).
- 30 s "2 AM burst pipe" story for owners: the hand-off cut with a voice-over, ends on "simulated call · transfer tested in dry-run" (O).
- 20 s "guardrail catches the model" clip: `book_job` refused, then `check_slots`, with a caption (T, A).
- 60 s screen recording of the call console: filter to hand-offs, open one, show the waterfall and redaction chips (C).

## Blog drafts (in `docs/ship/blog/`, not published)
1. `pipecat-twilio-phone-agent.md`: how a Pipecat phone agent on Twilio fits together (target: pipecat twilio phone agent).
2. `voice-agent-latency-breakdown.md`: where an AI phone agent's reply time goes, measured (target: voice agent latency).
3. `ai-receptionist-live-transfer.md`: live call transfer with a spoken summary (target: ai receptionist live transfer).
