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
  entity. The device appears under **Settings → Devices & services → Devices**,
  linked to the transmitter it's "connected through".
- Options flow (the device's **Configure** screen) to manage its contents:
  - **Codes** — a library of named IR/RF codes. Data only; creates no entity.
    A code is either a pasted Base64 payload or a **reference** to a command
    already learned on the remote (sent by name via `remote.send_command`, so
    it stays in sync). Add references with **Add remote command** (by name —
    works with any remote), or auto-populate them with **Import codes from
    remote** (a Broadlink-specific picker that reads its learned-command store).
  - **Buttons** — stateless button entities that each send one code.
  - **Switches** — optimistic (assumed-state) on/off switches built from codes.
    Pick the same code for both directions for a toggle-only appliance.
  - **Lights** — optimistic dimmable lights. Power is an on/off (or toggle)
    code; brightness is a set of absolute-level codes (e.g. 10%…100%). The
    brightness slider snaps to the nearest configured level.
  - **Climate** — optimistic heaters. Heat on/off (or toggle) code plus
    relative temperature up/down codes; the target-temp dial steps by firing
    up/down. Optionally link a sensor for the real current temperature.

A single device can mix any of these — e.g. a fireplace with a climate for
heat, a switch for the flame, and buttons for effects.

Planned next:

- Additional composite entity types (select, number, fan, ...).

## Installation (HACS)

1. Add this repository as a custom repository in HACS (category: *Integration*).
2. Install **Virtual RF/IR Device** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and search for
   *Virtual RF/IR Device*.
4. Give the appliance a name and pick the `remote` entity used to control it.

## Design

An IR/RF device is a flat bag of named codes, while Home Assistant wants
semantic, stateful entities. This integration separates the two concerns:

1. **Codes** are the raw material — a named library of IR/RF codes, no entities.
2. **Entities** (buttons, switches, and later select / number / fan / ...) are
   composed by referencing codes. Nothing appears on the device until you add
   one, so codes are never silently duplicated as controls.
