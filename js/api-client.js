(function (global) {
  'use strict';

  var activeRequests = {};

  function reportError(error) {
    if (error && error.name !== 'AbortError') {
      global.dispatchEvent(new CustomEvent('dashboard-api-error', { detail: error }));
    }
    throw error;
  }

  function parseJson(response) {
    if (response.status === 401) window.location.replace('/login');
    if (!response.ok) return response.json().then(function (data) {
      throw new Error(typeof data.detail === 'string' ? data.detail : 'HTTP ' + response.status);
    });
    return response.json();
  }

  function getJson(path, options) {
    options = options || {};
    return fetch(path, {
      headers: { Accept: 'application/json' },
      signal: options.signal
    }).then(parseJson).catch(reportError);
  }

  function getLatest(key, path) {
    if (activeRequests[key]) activeRequests[key].abort();
    var controller = new AbortController();
    activeRequests[key] = controller;
    return getJson(path, { signal: controller.signal }).finally(function () {
      if (activeRequests[key] === controller) delete activeRequests[key];
    });
  }

  function postJson(path, body) {
    return fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body)
    }).then(parseJson).catch(reportError);
  }

  global.dashboardApi = { getJson: getJson, getLatest: getLatest, postJson: postJson };
})(window);
