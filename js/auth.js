(function () {
  'use strict';
  var page = document.body.dataset.page;
  var status = document.getElementById('status');
  function message(text) { status.textContent = text; }
  function api(path, body) {
    return fetch(path, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body)
    }).then(function (response) {
      if (response.status === 401) { window.location.replace('/login'); throw new Error('Sessão encerrada.'); }
      return response.json().then(function (data) {
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível continuar.');
        return data;
      });
    });
  }
  function failure(error) { message(error.message || 'Não foi possível completar a solicitação.'); }
  var logout = document.getElementById('logout');
  if (logout) logout.addEventListener('click', function () {
    api('/auth/logout', {}).then(function () { window.location.replace('/login'); }).catch(failure);
  });
  if (page === 'login') {
    api('/auth/providers').then(function (providers) {
      document.getElementById('google').hidden = !providers.google;
      var root = document.getElementById('microsoft');
      providers.microsoft.forEach(function (domain) {
        var link = document.createElement('a');
        link.className = 'button provider';
        link.href = '/auth/login/microsoft?organization=' + encodeURIComponent(domain);
        link.textContent = 'Microsoft · ' + domain;
        root.appendChild(link);
      });
      var error = new URLSearchParams(window.location.search).get('error');
      message(error === 'domain' ? 'Sua organização não está autorizada a acessar este painel.' :
        error ? 'Não foi possível entrar. Tente novamente.' :
        (providers.google || providers.microsoft.length ? 'Escolha sua conta institucional para continuar.' : 'O acesso ainda não foi configurado. Entre em contato com o responsável pelo painel.'));
    }).catch(failure);
  } else {
    api('/auth/me').then(function (user) {
      document.getElementById('name').textContent = user.name;
      document.getElementById('identity').textContent = user.email + ' · ' + user.provider;
      message('Você está conectado.');
    }).catch(failure);
  }
})();
