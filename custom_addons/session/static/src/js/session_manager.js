odoo.define('session_manager.SessionManager', function (require) {
"use strict";

var core = require('web.core');
var Widget = require('web.Widget');
var session = require('web.session');

var SessionManager = Widget.extend({
    template: 'SessionManager.Widget',
    events: {
        'click .js_session_warning': '_onClickWarning',
    },

    init: function (parent, options) {
        this._super.apply(this, arguments);
        this.session_warning = options.session_warning || 30; // minutes
        this.session_timeout = options.session_timeout || 60; // minutes
        this.last_activity = new Date();
    },

    start: function () {
        this._setupActivityTracking();
        this._checkSessionTimeout();
        return this._super.apply(this, arguments);
    },

    _setupActivityTracking: function () {
        var self = this;
        $(document).on('click keydown mousemove scroll', function () {
            self.last_activity = new Date();
        });
    },

    _checkSessionTimeout: function () {
        var self = this;
        setInterval(function () {
            var inactive_min = (new Date() - self.last_activity) / (1000 * 60);
            if (inactive_min > self.session_timeout) {
                window.location = '/web/session/logout';
            } else if (inactive_min > self.session_warning) {
                self.$('.js_session_warning').removeClass('d-none');
            }
        }, 60000); // Check every minute
    },

    _onClickWarning: function (ev) {
        ev.preventDefault();
        this._rpc({
            model: 'session.manager',
            method: 'extend_session',
            args: [[], 1], // Extend 1 hour
        }).then(function () {
            location.reload();
        });
    },
});

core.action_registry.add('session_manager', SessionManager);

return SessionManager;
});