import Ember from 'ember';
import config from './config/environment';

var rootURL = null;
if (window.navigator.userAgent.match(/MSIE [6789]/)) {
  rootURL = '/' + config.baseURL + '/';
}

var Router = Ember.Router.extend({
  location: config.locationType
});

if (rootURL) {
  Router.reopen({
    rootURL: rootURL
  });
}

Router.map(function() {
  this.route('index', {resetNamespace: true, path: '/'});
  this.route('containers', {resetNamespace: true});

  this.route('account', {resetNamespace: true, path: '/shared/accounts'}, function() {
    this.route('container', {path: '/:account'}, function() {
      this.route('objects', {path: '/:container_name/*path'});
      // *path wont match an initial url with no path set 
      this.route('objects_redirect', {path: '/:container_name'});
    });
  });

  this.route('container', { resetNamespace: true, path: '/containers/:container_id'}, function(){
    this.route('objects', { path: '/*current_resetNamespace: true, path'}, function(){
      this.route('object', { resetNamespace: true, overrideNameAssertion: true }, function(){
        this.route('versions');
      });
    });
  });
  this.route('errors/404', {resetNamespace:true, path: '*path'});
});

export default Router;
