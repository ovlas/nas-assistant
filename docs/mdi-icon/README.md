# Sidebar icon for NAS Assistant — draft

`nas-assistant.svg` is a 24×24 single-colour version of the logo (house with a hard disk cut out of it),
for the Home Assistant sidebar.

Add-ons can only use `mdi:` icon names in `panel_icon`. There are two ways to get this one in:

## Route A — Material Design Icons (Pictogrammers)

Open an "Icon Request" issue on <https://github.com/Templarian/MaterialDesign/issues/new/choose>
with the SVG attached. Draft text:

> **Name:** `nas-assistant` (alias: `home-harddisk`)
>
> **Description:** A house with a hard disk inside: a home NAS / family cloud. Used by the NAS Assistant
> Home Assistant add-on (https://github.com/ovlas/nas-assistant) for its sidebar entry, and generally useful for
> "home storage", "home server" or "family cloud" concepts.
>
> **Draft:** attached SVG, 24×24, single colour. Happy to adapt it to the MDI grid and guidelines.

If accepted, it reaches Home Assistant with the next MDI release that Home Assistant adopts (usually months).
Asking for a generic icon (`home-harddisk`) has better chances than a brand logo.

## Route B — Home Assistant frontend

Music Assistant's sidebar icon (`mdi:music-assistant`) is not in MDI: it is built into the Home Assistant
frontend (`src/components/ha-icon.ts`, `CUSTOM_ICONS`). Adding `nas-assistant` there would need a pull request
to `home-assistant/frontend`; it is unlikely to be accepted for a community add-on.

Until then the add-on uses `mdi:harddisk`.
