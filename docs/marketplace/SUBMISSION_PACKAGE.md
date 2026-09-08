# Monster Truck Marketplace submission preparation

Prepared 2026-09-07. Working draft; no application or listing has been submitted.
Requested price: free, subject to Marketplace approval and partner pricing rules.

## Product description draft

**Proposed title:** Monster Truck Add-On

**Short description:** Craft a rugged two-seat Monster Truck, choose from six paint colors, and take on stepped terrain in your Bedrock worlds.

**Long description:** Build a Monster Truck for your next survival adventure! This lifted pickup features oversized tires, exposed suspension, an open cargo bed, and room for a driver and passenger. Start in red, then repaint your truck with yellow, blue, green, black, or white dye. Craft your vehicle in Survival, or try it with the Creative spawn egg. Engine audio and animated wheels bring the truck to life, while its heavy-duty construction and controlled two-block auto-step help it handle rough terrain.

Description is grounded in the current README and production assets. Player controls, audible playback, and two-player usability still need manual acceptance before these claims are submitted. Do not claim compatibility with every platform, every world, or every other add-on without evidence.

## Portfolio entry draft

Monster Truck is a data-driven Minecraft Bedrock vehicle add-on combining a two-seat rideable entity, procedural vehicle geometry, six paint textures, synthesized engine sounds, crafting, and survival mechanics. The project includes automated static checks and a separate runtime assertion pack used only in a dedicated test world. The distributable behavior pack contains no Script API module.

Representative media:

- [Six-color lineup](../images/monster-truck-colors.png)
- [Vehicle close-up](../images/monster-truck-closeup.png)
- [Player instructions and project showcase](../../README.md)

These local materials form one project entry. They do not establish a public portfolio, audience size, community history, previous releases, or partner eligibility.

## Partner application narrative draft

I am developing Monster Truck, a Minecraft Bedrock Add-On that introduces a craftable, two-seat vehicle with six paint colors, engine audio, and controlled terrain stepping. I would like to make it available as a free Add-On through the official Minecraft Marketplace.

The project includes repository-owned modeling and texture generation, synthesized audio, documented player instructions, and automated validation. A separate test-world harness checks vehicle behavior without distributing test scripts to players. I can provide a packaged build, gameplay screenshots, and test evidence for review.

Please advise on the current Marketplace creator application process, whether new independent creators are being accepted, and the approval process for a zero-price Add-On.

This is draft wording only; no inquiry has been sent. Creator identity, contact information, public portfolio links, and ownership assertions must come from the applicant.

## Media production brief

Existing screenshots are candidates, not certified Marketplace key art. Obtain current partner asset dimensions and branding requirements before final export.

Proposed 30-second gameplay trailer:

| Time | Actual footage to capture | Caption |
| --- | --- | --- |
| 0-5s | Three-quarter view of red truck | Monster Truck Add-On |
| 5-10s | Six-color lineup followed by a real dye interaction | Six paint colors |
| 10-17s | Player driving over a two-block stepped obstacle | Built for rough terrain |
| 17-23s | Two players boarding and riding | Bring a passenger |
| 23-28s | Crafting and deploying the vehicle in Survival | Craft. Customize. Drive. |
| 28-30s | Clean hero view | Creator name to be supplied |

Capture retail gameplay with the distributed pack; retain original footage. Use game audio only after playback verification. Do not substitute a screenshot slideshow for gameplay proof or show an unapproved Marketplace availability badge. A trailer has not yet been recorded.

## Asset provenance inventory

| Asset group | Repository evidence | Remaining confirmation |
| --- | --- | --- |
| Vehicle geometry | `scripts/make_truck_geometry.py`; exported `monster_truck.geo.json` | Applicant confirms authorship/contributor rights and any external references |
| Six vehicle textures | `scripts/make_placeholder_textures.py`; production entity PNGs | Confirm current exports originate from authorized sources |
| Engine sound effects | `scripts/generate_audio.py` synthesizes waveforms and converts with ffmpeg | Confirm shipped OGG files derive from this source or supply alternative licenses |
| Behavior, recipes, animations | Repository JSON and scripts | Identify contributors and any copied source requiring attribution |
| Screenshots | Existing in-game captures under `docs/images/` | Approve selected images; check final export rules |
| Test world starter | `testing/world-template.LICENSE.txt` | Test-only material; exclude world and harness from the release |

Repository source is evidence of a production path, not a legal certification of ownership. No license or rights declaration has been invented on behalf of the creator.

## Release acceptance work

- [ ] Retail Windows runtime test finishes with clean content logs.
- [ ] Inspect newly captured images for geometry, textures, seating, and clipping.
- [ ] Confirm keyboard driving, dye interaction, crafting, deployment, retrieval, and audible engine sounds manually.
- [ ] Verify driver and passenger with two real players; controller and touch input on intended devices.
- [ ] Test existing-world activation, save/reload, pack updates, and coexistence with representative other add-ons.
- [ ] Run official Creator Tools validation and review findings; local pytest is not Marketplace certification.
- [x] Verify release archive excludes test harness, local configuration, and test world; see [release evidence](RELEASE_EVIDENCE.md).
- [ ] Complete ownership confirmations, creator identity, contact, and portfolio links.
- [ ] Produce final key art and gameplay trailer to the partner specifications.
- [ ] Confirm a working Marketplace application channel and submit an accurate application.
- [ ] After partner acceptance, submit the content for Minecraft review and free-price approval.

## Official sources and current route

The [Minecraft Partner Program](https://www.minecraft.net/en-us/partner) requires original portfolio work, business readiness, promotional materials, and quality/suitability review. Its public page inspected on 2026-09-07 did not expose an Apply button. Do not interpret the page as proof that applications are currently open.

The [official partnership proposal form](https://partnerships.minecraft.net/hc/en-us/requests/new) is a candidate contact surface. Its initial menu was inspected, but Marketplace-specific intake has not yet been confirmed; do not submit to a licensing category as though it were creator onboarding.

[Minecraft Creator Tools](https://learn.microsoft.com/en-us/minecraft/creator/documents/mctoolsoverview?view=minecraft-bedrock-stable) provides validation; its results do not replace partner review. Additional cited background is in [the research note](../MARKETPLACE_PUBLICATION_RESEARCH.md).
