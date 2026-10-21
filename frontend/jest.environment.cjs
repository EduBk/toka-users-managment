const { TestEnvironment } = require('jest-environment-jsdom');

// jsdom does not expose these Node globals; React Router data routers need them.
class JsdomWithNodeGlobals extends TestEnvironment {
  constructor(...args) {
    super(...args);
    Object.assign(this.global, {
      Request,
      Response,
      Headers,
      AbortController,
      AbortSignal,
      TextEncoder,
      TextDecoder,
    });
  }
}

module.exports = JsdomWithNodeGlobals;
