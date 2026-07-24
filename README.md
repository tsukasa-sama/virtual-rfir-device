# Virtual RF/IR Device

A Home Assistant custom integration that turns an IR/RF-controlled appliance
(a fireplace, fan, projector, LED candle, blinds, ...) into its own Home
Assistant **device** with proper control entities — instead of exposing a raw
grid of remote buttons.

Commands are transmitted through an existing `remote` entity (e.g. a Broadlink
transmitter), so the physical hub stays the hardware while the appliance
becomes a first-class virtual device.

## Status

Early development. Current capability:

- Config flow to create a named virtual device bound to an IR/RF `remote`
  entity. After picking the remote you choose which **command group** on it this
  device represents — the remote stores learned commands under top-level groups
  (a Broadlink "device", e.g. `great_room_fireplace`), and the virtual device is
  scoped to one so only its commands are offered. The device appears under
  **Settings → Devices & services → Devices**, linked to the transmitter it's
  "connected through".
- Options flow (the device's **Configure** screen) to build its controls from
  that group's **learned commands**. The commands are read **live** each time a
  picker is shown; a control stores only the command's name and transmits it by
  name via `remote.send_command` (within the chosen group). Because nothing is
  copied, re-learning a command updates every control that uses it — no
  reconfiguration, no stale copy. Control types:
  - **Buttons** — stateless button entities that each send one command.
  - **Switches** — optimistic (assumed-state) on/off switches. Pick the same
    command for both directions for a toggle-only appliance.
  - **Lights** — optimistic dimmable lights. Power is an on/off (or toggle)
    command. Dimming is one of: **preset** (a code per absolute level, e.g.
    10%…100% — the slider snaps to the nearest), **relative** (`brightness_up` /
    `brightness_down` codes stepped across a list of percentages, like the
    climate dial), or **none** (on/off only). Brightness is inert while the
    light is off — adjusting it snaps back; turn the light on first. A power-on
    option decides whether the light resumes its last brightness or drives to
    full when switched on.
  - **Climate** — optimistic heaters/coolers. A mode command per enabled mode
    (heat and/or cool) plus relative temperature up/down commands; the
    target-temp dial steps by firing up/down. Optionally link a sensor for the
    real current temperature.

A single device can mix any of these — e.g. a fireplace with a climate for
heat, a switch for the flame, and buttons for effects.

**Device settings** (the **Device settings** menu item) include a *tick delay* —
the pause between consecutive relative presses (climate temperature and relative
light dimming). Rapid adjustments are serialized so they never interleave; the
delay adds a gap on top so the appliance reliably registers each step.

> **Reading learned commands is Broadlink-specific for now.** The live picker
> reads Broadlink's learned-command store (`.storage/broadlink_remote_<mac>_codes`).
> Sending is remote-agnostic (any remote that resolves commands by name), but
> other remotes won't populate the picker until an adapter for their store is
> added.

Planned next:

- Additional composite entity types (select, number, fan, ...).
- Adapters to read learned commands from remotes other than Broadlink.

## Installation (HACS)

1. Add this repository as a custom repository in HACS (category: *Integration*).
2. Install **Virtual RF/IR Device** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and search for
   *Virtual RF/IR Device*.
4. Give the appliance a name and pick the `remote` entity used to control it.

## Design

An IR/RF remote is a flat bag of named learned commands, while Home Assistant
wants semantic, stateful entities. This integration composes the latter from
the former without ever copying:

1. **Learned commands** are the raw material — they live in the remote's own
   store, not here. They're read live whenever you configure a control.
2. **Entities** (buttons, switches, lights, climate, and later select / number
   / fan / ...) are composed by pointing at a learned command. An entity stores
   only the pointer and sends by name, so the remote resolves the current code
   every time. Re-learning a command flows through automatically; nothing is
   snapshotted into this integration's config.
