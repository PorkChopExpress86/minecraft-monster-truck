# Publishing a Bedrock Add-On to Minecraft Marketplace

**Research date:** 2026-09-07
**Scope:** the official Minecraft Marketplace for Bedrock content, not the separate Microsoft commercial marketplace/Partner Center for business software.

## Short answer

An independent creator cannot self-publish a Bedrock add-on merely by creating an `.mcaddon` file or opening a general Microsoft Partner Center account. Marketplace is a curated Bedrock-content store whose content is made by *community creator partners*. The public route is to become an approved **Minecraft Partner**, then submit content through the partner process. Minecraft says every new submission is reviewed for quality and suitability before players can obtain it.

* [What is Marketplace?](https://www.minecraft.net/en-us/article/what-minecraft-marketplace) describes Marketplace as a library of content by community creator partners for Bedrock Edition.
* [Minecraft Partner Program](https://www.minecraft.net/en-us/partner) is the authoritative public starting point for prospective publishers; the [Marketplace FAQ](https://feedback.minecraft.net/hc/en-us/articles/360004166751-Marketplace-FAQ) points prospective partners to it.

## Marketplace versus an ordinary Bedrock add-on package

| Topic | What the official documentation establishes |
| --- | --- |
| Bedrock add-on | A behavior pack and/or resource pack that changes Bedrock content or behavior. A locally distributed `.mcpack` imports a pack; an `.mcworld` may contain add-ons. [Getting Started with Add-Ons](https://learn.microsoft.com/en-us/minecraft/creator/documents/gettingstarted?view=minecraft-bedrock-stable) |
| `.mcaddon` | A packaged bundle of scripts/assets. The official development workflow says `npx just-scripts mcaddon` builds, bundles, and packages an add-on “for distribution in the marketplace.” It should be tested after packaging. [Add-On Development Workflow](https://learn.microsoft.com/en-us/minecraft/creator/documents/addondevelopmentworkflow?view=minecraft-bedrock-stable) |
| Marketplace listing | A store offering delivered through Minecraft Marketplace, available only from an approved creator partner and reviewed before release. Marketplace now explicitly includes **Add-Ons** among its shop content. [Marketplace navigation and categories](https://www.minecraft.net/en-us/usage-guidelines) |

**Important boundary:** the public documentation does *not* say that uploading an `.mcaddon` to a public web form creates a Marketplace listing, nor does it publish the exact partner submission file format. Treat `.mcaddon` as a tested distributable build artifact, not evidence of Marketplace acceptance.

## Partner onboarding: what an applicant should prepare

Minecraft publicly describes these selection criteria:

1. **Proven experience:** a portfolio of high-quality, original Minecraft community content; the examples explicitly include add-ons.
2. **Community engagement and creative drive:** the applicant should participate in the community and keep creating and testing ideas.
3. **Business readiness:** an applicant is expected to operate like a business and provide key art, screenshots, trailers, and descriptions; Minecraft says those are needed for the application as well.

Source: [Minecraft Partner Program criteria](https://www.minecraft.net/en-us/partner).

Practical preparation, limited to that public evidence:

- Publish or otherwise assemble an original, demonstrably high-quality portfolio before applying.
- Have a clear creator/studio identity and contact/support path.
- Prepare representative gameplay media plus key art, screenshots, trailer, and accurate description.
- Apply through the current contact/application path exposed by the official **Minecraft Partner Program** page. Do not use the general Microsoft commercial Marketplace enrollment flow; it documents Azure/Microsoft 365 offers, not Minecraft content.

## Content, quality, and rights requirements

### Publicly verified requirements

- A Marketplace submission undergoes quality-and-suitability review. The public partner page does not expose its full rubric. [Partner Program](https://www.minecraft.net/en-us/partner)
- Content must be compatible with the claimed target devices. Minecraft warns that maps/textures needing more resources can be unavailable on devices with under 512 MB RAM; this is player-facing compatibility evidence, not a published add-on certification limit. [Marketplace FAQ](https://feedback.minecraft.net/hc/en-us/articles/360004166751-Marketplace-FAQ)
- Minecraft Creator Tools includes validation rules that specifically cover sharing/Marketplace concerns. Its sharing suite reports custom capabilities (including experiments/Beta APIs) that may limit distribution, and warns on strong language. [Sharing validation rules](https://learn.microsoft.com/en-us/minecraft/creator/reference/content/mctoolsvalreference/sharing?view=minecraft-bedrock-stable)
- Minecraft's public EULA says creators retain their original content, while Mojang/Microsoft retains its own code and content; creators must not distribute or commercially use Minecraft material without permission. Marketplace partnership is the relevant permission path for paid Marketplace distribution. [Minecraft EULA](https://www.minecraft.net/en-us/eula)
- Content that portrays hate/extreme bias or encourages illegal activity is not permitted, and Minecraft has zero tolerance for hate speech, extremist content, bullying/harassment, sexual solicitation, fraud, and threats. [Minecraft EULA and Community Standards](https://www.minecraft.net/en-us/eula)

### Sound technical readiness checklist

Before submitting to a partner channel:

- Build a release candidate and import it into the current retail Bedrock client; ensure all packs load without content-log errors.
- Use the documented build-test-iterate cycle; test each feature, translations, multiplayer, coexistence with other add-ons, and representative survival/difficulty settings. [Development workflow testing guidance](https://learn.microsoft.com/en-us/minecraft/creator/documents/addondevelopmentworkflow?view=minecraft-bedrock-stable)
- Run Minecraft Creator Tools validation (`npx mct validate <project>` or the Inspector). It supports `.mcaddon`, `.mcpack`, and suitable ZIP inputs; validation helps find issues but is not a Marketplace approval guarantee. [Creator Tools overview](https://learn.microsoft.com/en-us/minecraft/creator/documents/mctoolsoverview?view=minecraft-bedrock-stable)
- Test performance on intended device classes. Microsoft recommends fewer than 800 texture handles for add-ons and preferably under 100 MB uncompressed (under 200 MB recommended upper guidance); these are recommendations, not declared Marketplace limits. [Performance and resource usage](https://learn.microsoft.com/en-us/minecraft/creator/documents/practices/improvingperformanceandresourceusage?view=minecraft-bedrock-stable)
- Version the manifest and release materials consistently; the official workflow recommends semantic versioning and documenting breaking world-compatibility changes. [Development workflow release guidance](https://learn.microsoft.com/en-us/minecraft/creator/documents/addondevelopmentworkflow?view=minecraft-bedrock-stable)

## Submission, review, publication, and monetization

The public flow that can be stated confidently is:

1. Build an original, tested Bedrock add-on and a portfolio/application package.
2. Apply to the Minecraft Partner Program using its current official route.
3. If accepted, submit each proposed Marketplace item through the partner process with the required promotional assets and description.
4. Minecraft reviews every new submission for quality and suitability.
5. Once released, players acquire Marketplace content using Minecoins (with Tokens on PlayStation in the cited Marketplace explainer).

Sources: [Partner Program](https://www.minecraft.net/en-us/partner), [What is Marketplace?](https://www.minecraft.net/en-us/article/what-minecraft-marketplace).

**Not publicly specified (do not invent these):** the current application form/eligibility thresholds; legal entity, tax, banking, age, or country requirements; revenue-share percentage; price-setting rules; partner contract terms; detailed asset dimensions; private submission portal; review SLA; rejection/appeal procedure; and exact update/certification steps. These may be provided during/after partner onboarding or change without a public announcement. Obtain them directly from Minecraft before making a business commitment.

## Recommended next action for this add-on

Finish a retail-tested, validator-clean release candidate; build a small public portfolio demonstrating the monster truck's original assets and gameplay; then use the official [Minecraft Partner Program](https://www.minecraft.net/en-us/partner) page to begin the current partner inquiry/application. Prepare an honest feature description and gameplay media that match the exact build, and retain proof that all third-party models, textures, sounds, trademarks, and brands are licensed for the intended commercial Marketplace use.
