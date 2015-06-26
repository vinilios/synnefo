import DS from 'ember-data';
import Ember from 'ember';

export default DS.RESTSerializer.extend({
  extract: function(store, type, payload) {
    if (_.isEmpty(payload.uuid_catalog) && !_.isEmpty(payload.displayname_catalog)) {
      var userEmail = Object.keys(payload.displayname_catalog)[0];
      return {
        'id': payload.displayname_catalog[userEmail],
        'uuid': payload.displayname_catalog[userEmail],
        'email': userEmail
      }
    }
    else if (!_.isEmpty(payload.uuid_catalog) && _.isEmpty(payload.displayname_catalog)) {
      var userId = Object.keys(payload.uuid_catalog)[0];
      return {
        'id': userId,
        'uuid': userId,
        'email': payload.uuid_catalog[userId]
      }
    }
    else {
      console.log('%cError: User not found!', 'color:red');
      throw new Error('Not found');
    }
  }
});
