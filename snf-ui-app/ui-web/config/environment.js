/* jshint node: true */

module.exports = function(environment) {
  environment = environment || 'development';

  var ENV = {
    djangoContext: true,
    modulePrefix: 'ui-web',
    environment: environment,
    baseURL: 'ui',
    locationType: 'auto',
    contentSecurityPolicy: {
      'style-src': "'self' 'unsafe-inline' fonts.gstatic.com *.googleapis.com",
      'font-src': "'self' fonts.gstatic.com",
      'report-uri': 'http://localhost:4200',
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
        myOption: 'my-option',
      // Here you can pass flags/options to your application instance
      // when it is created
    }
  };
  
  if (environment.match('development')) {
    // ENV.APP.LOG_RESOLVER = true;
    ENV.APP.LOG_ACTIVE_GENERATION = true;
    // ENV.APP.LOG_TRANSITIONS = true;
    // ENV.APP.LOG_TRANSITIONS_INTERNAL = true;
    ENV.APP.LOG_VIEW_LOOKUPS = true;
    ENV.APP.emberDevTools = {global: true};
  }

  if (environment.match('local|test')) {
    ENV.djangoContext = false;

    ENV.appSettings = {
      uuid: 'user-uuid',
      token: 'token',
      account_url: '/accounts',
      storage_host: '/object-store/v1/user-uuid',
      storage_url: '/object-store/v1',

      logo_url: new Buffer('aHR0cDovL2kyLmt5bS1jZG4uY29tL3Bob3Rvcy9pbWFnZXMvb3JpZ2luYWwvMDAwLzExNy80MjQvdHVtYmxyX2xqd2FpbWhKY0sxcWE0ZWJmbzFfNTAwLmdpZg==', 'base64').toString('ascii'),
    }
  }

  if (environment === 'test') {
    ENV.djangoContext = false;
    // Testem prefers this...
    ENV.baseURL = '/';
    ENV.locationType = 'auto';

    // keep test console output quieter
    ENV.APP.LOG_ACTIVE_GENERATION = false;
    ENV.APP.LOG_VIEW_LOOKUPS = false;

    ENV.APP.rootElement = '#ember-testing';
  }

  if (environment.match('production')) {

  }

  return ENV;
};
