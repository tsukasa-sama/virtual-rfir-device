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

- **v0.1** — Config flow to create a named virtual device bound to an IR/RF
  `remote` entity. The device appears under **Settings → Devices & services →
  Devices**, linked to the transmitter it's "connected through".

Planned next:

- Button controls (one entity per stored command).
- Composite semantic entities (switch, select, number, fan, ...) that bind
  commands to Home Assistant roles.

## Installation (HACS)

1. Add this repository as a custom repository in HACS (category: *Integration*).
2. Install **Virtual RF/IR Device** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and search for
   *Virtual RF/IR Device*.
4. Give the appliance a name and pick the `remote` entity used to control it.

## Design

An IR/RF device is a flat bag of named commands, while Home Assistant wants
semantic, stateful entities. This integration resolves that with a two-layer
model:

1. **Every command is a button** — a universal, zero-config baseline.
2. **Optional composite entities** — switch / select / number / fan / etc. that
   bind command names to entity roles.
