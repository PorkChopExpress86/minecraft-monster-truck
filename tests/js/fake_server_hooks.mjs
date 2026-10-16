export function resolve(specifier, context, nextResolve) {
  if (specifier === "@minecraft/server") {
    return {
      url: new URL("./fake_server.mjs", import.meta.url).href,
      shortCircuit: true,
    };
  }
  return nextResolve(specifier, context);
}
