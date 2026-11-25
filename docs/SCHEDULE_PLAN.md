# Plan: making scheduling simple (Witching Hour + The Horde)

Status: **proposal, waiting for the owner's approval.** Nothing here is built yet.

## What is wrong today

The Schedule page asks you to understand about fifteen things at once, in this order:

1. Three pre-flight switches (scheduler daemon, keep PC awake, Safe-Publish Gate), then three platform login checks.
2. A builder with eight fields: videos, first upload, date and time, spacing, custom spacing, render timing, minutes before upload, platforms, visibility.
3. A queue where every card shows four progress steps, a late badge and three or four buttons.
4. Time zone, daily caps and a raw event log.

Three questions get mixed together: **is the lab ready to run alone, what do I want posted and when, and what is happening right now.** Batch adds a second way into the same queue (`auto_publish` rows) with its own interval and start-time fields.

## The plan: one question per part of the page

### 1. "Tonight" header: what is happening (always visible)
A night-sky strip across the top. It shows the next 24 hours as a timeline, with each upload as a moon marker (violet for scheduled, candle for held, blood for failed). One sentence sits above it: *"3 uploads tonight · next at 11:00 PM · the lab is awake"*. Clicking a marker scrolls to that video's card.

### 2. "Ready for the night?" (one line, not three panels)
The pre-flight collapses into a single readiness bar of chips: **Night watch** (scheduler), **Stays awake**, **Fact gate**, then **YouTube, Instagram, TikTok** logins. Green chips need nothing. A grey or red chip opens its fix in place. **Make it ready** turns on everything that can be turned on in one click. The bar disappears completely when everything is green.

### 3. "Add to the night": a 3-step drawer instead of an 8-field form
Opened from this page, from **Add to Schedule** in Dracula's Vault, and after a render finishes on the Operating Table, already filled in with that video.

| Step | Asks | Defaults |
| --- | --- | --- |
| 1. What | Pick videos from the **Alive** shelf (rendered). Scripts from **On the slab** can be added too; they render shortly before their slot. | The video you came from |
| 2. When | Presets: **Tonight from 9 PM, 1 per hour**, **Tomorrow morning**, **Spread over the week**, or **Custom** (first slot + spacing). A live timeline preview shows exactly where each video lands and warns about daily caps. | Tonight, hourly |
| 3. Where | Platforms and YouTube visibility. | YouTube, unlisted |

Advanced options (render lead time, custom spacing) live behind "More options" in step 2.

### 4. The queue, grouped the way you think about it
Group cards by **Needs you** (held by the gate, late, failed: always first), **Tonight**, **Tomorrow**, **Later** and **Done**. Each card has one status sentence ("Uploads to YouTube at 11:00 PM", "Held: 2 facts to check") and one primary button that fits its state (Approve, Retry, Run now). Pause, Remove and the step detail go into a small menu.

### 5. Rules of the night (rarely touched)
Time zone, daily caps per platform and the event log move into a collapsed "Rules of the night" section at the bottom. Time zone and caps also appear in The Apothecary.

### Batch (The Horde) uses the same pieces
After a sheet is validated, Batch shows the same **When** step (presets plus timeline preview) for rows marked `auto_publish`. There is one way to choose times across the whole app. Rows with their own `schedule_at` show as pinned markers on the timeline.

## Build order (after approval)
1. The shared **When** step plus the timeline preview, used by Schedule and Batch.
2. The add drawer and its entry points (Vault, Operating Table, Schedule).
3. The grouped queue cards.
4. The readiness bar and the Tonight strip.
5. Moving the rules section, then running the 4-viewport audit and the page-switch check.

No backend changes are needed for 1 to 4: the builder and queue APIs (`/api/schedule/*`) already have everything. The "Spread over the week" preset is computed in the browser.

## Questions for the owner
1. Should un-rendered scripts be schedulable (they render just before their slot, so the PC must stay on), or only finished videos?
2. Should the default night window be 9 PM to 6 AM, or do you prefer other hours?
3. Should **Make it ready** also turn on "Stays awake" (the PC does not sleep while jobs are pending)?
