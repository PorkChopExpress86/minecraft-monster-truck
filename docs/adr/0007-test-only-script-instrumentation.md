# Separate test-only script instrumentation

Use a separate Script API behavior pack in the dedicated Windows test world to positively verify Monster Truck spawning and emit a run-specific result. This trades additional test-environment setup for runtime evidence that does not depend on interpreting screenshots or command-entry keystrokes. The harness stays outside the distributable add-on, preserving ADR-0001's data-only production architecture; visual, audio, and driving checks remain part of the proving-ground review.
