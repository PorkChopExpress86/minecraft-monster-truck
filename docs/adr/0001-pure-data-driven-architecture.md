# Pure Data-Driven Architecture for Vehicle Mechanics

We decided to keep the Monster Truck add-on strictly data-driven using Bedrock entity JSON definitions, animation controllers, and client entity resources, deliberately rejecting the Bedrock Script API (`@minecraft/server`) for this phase. This trade-off prioritizes universal cross-platform compatibility (consoles, mobile, Windows) with zero required experimental toggles and eliminates dependencies on rapidly evolving Script API module versioning.
