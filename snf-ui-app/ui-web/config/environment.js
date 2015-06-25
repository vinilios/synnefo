/* jshint node: true */

module.exports = function(environment) {
  var ENV = {
    djangoContext: true,
    appSettings: {},
    modulePrefix: 'ui-web',
    environment: environment,
    baseURL: 'ui',
    locationType: 'auto',
    contentSecurityPolicy: {
      'style-src': "'self' 'unsafe-inline' fonts.gstatic.com *.googleapis.com",
      'font-src': "'self' fonts.gstatic.com",
      'img-src': "'self' *.kym-cdn.com data:",
      'script-src': "'self' 'unsafe-eval' 'unsafe-inline'"
    },
    EmberENV: {
      FEATURES: {
        // Here you can enable experimental features on an ember canary build
        // e.g. 'with-controller': true
      }
    },

    APP: {
      defaultLocale: 'en',
      // Here you can pass flags/options to your application instance
      // when it is created
    }
  };

  if (environment === 'development') {
    // ENV.APP.LOG_RESOLVER = true;
    ENV.APP.LOG_ACTIVE_GENERATION = true;
    ENV.APP.LOG_TRANSITIONS = true;
    ENV.APP.LOG_TRANSITIONS_INTERNAL = true;
    ENV.APP.LOG_VIEW_LOOKUPS = true;
    ENV.APP.emberDevTools = {global: true, enabled: false};
  }

  if (environment === 'test') {
    // Testem prefers this...
    ENV.djangoContext = false;
    ENV.appSettings = {
      token: 'TEST-TOKEN',
      auth_url: '/api/identity'
    };
    ENV.baseURL = '/';
    ENV.locationType = 'none';

    // keep test console output quieter
    ENV.APP.LOG_ACTIVE_GENERATION = false;
    ENV.APP.LOG_VIEW_LOOKUPS = false;

    ENV.APP.rootElement = '#ember-testing';
  }

  if (environment === 'production') {

  }

  return ENV;
};
