# Step 0 research: Blue Ridge phone agent ship (2026-11-05)

Most web sources are vendor blogs; numbers from them are directional only and are NOT used in any copy.

## 1. Branding
Findings
- Niche + outcome positioning beats "AI agency" generalism; "we use AI" is no longer a differentiator.
  https://ciela.ai/blogs/should-you-niche-down-or-go-general-ai-agency · https://www.ertas.ai/blog/niche-ai-agency-vs-generalist
- Upwork thumbnails: high contrast, one centred subject, readable at small size; strongest niche piece first.
  https://www.upwork.com/resources/portfolio-guide · https://help.gigradar.io/en/articles/8370550-the-best-guide-for-an-upwork-portfolio-that-ever-existed
- Voice-agent gigs on Upwork/Fiverr all look alike: dark navy, neon blue/purple, robot/headset art. Contrast is the opening.

Audit of the existing adelatya brand
- site.css tokens: paper #F7F4EE / #EFE9DC / #E4DCCB, ink #16130F / #3A342C, grey #6B655B, red #C63C22, red-lift #F2643F,
  gradient red-lift -> red. Type: Archivo (700/800, tight tracking) + Instrument Serif italic in red for emphasis words.
  Radii 18/12, hard warm shadows. Label style: caps, letter-spaced, red, with a 28px red rule.
- aa-social/BRAND.md: "a trade business at night, not a sci-fi poster". Never neon, purple/teal tech gradients, robots.
  AA monogram top-right; footer "AA · AI VOICE AGENTS".
- Gap: the phone-agent console and video use #0f1419 navy + #60a5fa blue + IBM Plex. That is exactly the "AI neon"
  look the brand bans, and nothing in them says adelatya.

## 2. What buyers ask for (mapped to the 13 features)
- Upwork posts: Twilio telephony, CRM push (GHL / HubSpot / Zoho), inbound + outbound, appointment setting, call transfer
  to a live person, prompt engineering. Vapi/Retell/GHL dominate titles; Pipecat/LiveKit appear in technical builds.
  https://www.upwork.com/freelance-jobs/apply/Voice-Agent-Developer-Vapi-Twilio-GoHighLevel-Inbound-and-Outbound-Builds_~022074145228337932723/
  https://www.upwork.com/freelance-jobs/apply/Voice-Agent-Developer-Retell-Vapi-Twilio-GoHighLevel-Expert-Needed_~022064167598190527775/
  https://www.upwork.com/freelance-jobs/apply/GoHighLevel-Voice-Agent-CRM-Automation-Setup-for-Startup_~022074669835156389351/
- Buyer worries: (a) pauses make it feel fake, ask for END-TO-END latency (F1, F12); (b) cold transfers where the caller
  repeats everything, want a handoff with context (F6); (c) must write into the real calendar/CRM (F2, F5);
  (d) after-hours emergencies (F7); (e) cost vs answering service (F13).
  https://www.forasoft.com/blog/article/ai-receptionist-development · https://skoreflow-site-preview.pages.dev/blog/ai-receptionist-checklist/
  https://www.nextiva.com/blog/ai-answering-service-adoption-barriers.html
- Buyer vocabulary: "warm transfer", "books into your CRM", "24/7", "after-hours", "no hold", "end-to-end latency",
  "own your stack / no platform fee", "self-hosted".
- Own-stack angle: Vapi charges a platform fee per minute on top of providers; Pipecat is BSD-2 open source. Vendor
  break-even claims (Dograh) are biased, so copy says only "no per-minute platform markup", no savings %.
  https://blog.dograh.com/self-hosted-voice-agents-vs-vapi-real-cost-analysis-tco-break-even/
  https://livekit.com/field-guides/guide/livekit-vs-pipecat

## 3. Targeting
| Segment | Where | Hook |
|---|---|---|
| Technical buyers: SaaS / voice startups wanting their own stack | Upwork search "Pipecat", "LiveKit", "Twilio Media Streams", "voice AI engineer"; LinkedIn CTO / Head of Eng; Pipecat Discord | "Your own voice stack, not a rented one" (F13, F12, F9) |
| Agencies reselling voice (GHL white-label) | LinkedIn agency owners, GHL communities | "A voice layer you can brand, with handoff and CRM sync built in" (F5, F6) |
| Home-services owners (plumbing, HVAC) | Google (blog), Facebook trade groups, local | "Burst pipe at 2am: it answers, gives safety advice, rings your on-call tech" (F7, F6, F1) |
| Call centres / ops leads | LinkedIn ops titles | "Every call timed, redacted and graded" (F11, F12) |
GHL now bundles its own voice AI, so agencies are buyers of custom work, automation shops are competitors (memory).
https://viirtue.com/gohighlevel-voice-ai-white-label-vs-viirtue-reselling-voice-ai-agents-compared/

## 4. LinkedIn
- Document carousels (PDF) lead on dwell time and reach; short native video (under 90 s) second; links in the post body
  cut reach, so put the repo link in the first comment.
  https://www.oktopost.com/blog/linkedin-carousel-pdf-best-practices/ · https://www.dataslayer.ai/blog/linkedin-algorithm-february-2026-whats-working-now
  https://ciela.ai/blogs/linkedin-content-types-ranked
- Plan: Featured = the video + repo; Project entry with skills; 5 posts = 2 carousels, 2 native videos, 1 text+image.

## 5. Blog / SEO
- Home-services "AI receptionist for plumbers/HVAC" is crowded with vendor roundups (open.cx, lunacal, stork, myaifrontdesk).
  https://lunacal.ai/blogs/ai-receptionist-for-plumbers · https://www.open.cx/blog/ai-for-plumbers-2026
- Less crowded, fits this project: "Pipecat Twilio phone agent" (tutorial), "Vapi alternative self-hosted",
  "voice agent latency breakdown", "AI receptionist live transfer warm handoff". These match technical buyers.
- Existing blog: 10 posts, daily cloud writer, PLAYBOOK.md + RUBRIC.md gate (90+). Its fact list says "answers in about
  1 second" (that is the Retell demo). The phone-agent posts must use 1.74 s median and say simulated.

## 6. Upwork
- Valid skill tags (ship-voice-project skill): AI Agent Development, Conversational AI, API Development, Python,
  Automation (+ Chatbot Integration, NLP). Not tags: Vapi, Retell AI, Voice AI, Webhooks. Catalog search tags are free text,
  so "Pipecat", "Twilio" work there.
- Top voice listings lead with stack names + "books into your CRM"; few show measured numbers. Measured latency + honest
  limits is the differentiator.
  https://www.upwork.com/services/product/development-it-an-ai-voice-agent-that-calls-qualifies-and-books-leads-into-your-crm-2090204803797359372

## Decisions (Adel, 2026-11-05)
- Brand proposal approved: ink #16130F / paper #F7F4EE / red #C63C22 -> #F2643F, Archivo + Instrument Serif italic accent,
  IBM Plex Mono only for timings and tool calls, AA mark top-right, footer "AA · AI VOICE AGENTS".
- Thumbnail: "Answers in *1.7 s*." with small mono text under it: "median, simulated calls".
- "Your own voice stack, not a rented one" goes on technical-buyer assets only (not owner/agency posts).
