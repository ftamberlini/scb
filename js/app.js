/* Bilheteria Cinema Brasil — app.js (vanilla JS, no framework)
   Loads d3 + topojson (CDN) and country-data.js (window.CINEMAP_COUNTRY_ROWS). */
(function () {
  'use strict';

  /* ---------------- Data ---------------- */
  var GENRE_COLORS = {
    'Drama':'#efa838','Romance':'#5b9bf0','Thriller':'#a06bf0','Horror':'#3fbf9a',
    'Comedy':'#ef6b8b','Action':'#ef5b5b','Sci-Fi':'#3fc7df','Fantasy':'#b6d94c',
    'Animation':'#df5bc7','Documentary':'#9aa6b8'
  };
  var ML_GENRES = ['Action','Adventure','Animation','Children','Comedy','Crime','Documentary','Drama','Fantasy','Film-Noir','Horror','IMAX','Musical','Mystery','Romance','Sci-Fi','Thriller','War','Western','(no genres listed)'];
  var IMDB_GENRES = ['Action','Adult','Adventure','Animation','Biography','Children','Comedy','Crime','Documentary','Drama','Family','Fantasy','Film-Noir','Game-Show','History','Horror','Music','Musical','Mystery','News','Reality-TV','Romance','Sci-Fi','Short','Sport','Talk-Show','Thriller','War','Western'];
  var YEARS = []; // populated from Oracle data after load
  var RATINGS_DIST = []; // [{rating, votes}] from /api/ratings-dist
  var PERIODO_OPTIONS = { anos: [], semanas: [] }; // from /api/ancine/periodo-options
  var OBRA_OPTIONS = { paisOrigem: [] }; // from /api/ancine/obra-options
  var SALA_OPTIONS = { combos: [] }; // from /api/ancine/sala-options — [{grupoExibidor, uf, municipio}]
  var GENDERS = ['Male','Female','Unknown'];
  var RACES = ['WHITE','ASIAN','BLACK','INDIGENOUS','MIXED-RACE','UNKNOWN'];
  var RACE_COLORS = {WHITE:'#cdbba0',ASIAN:'#e0b54a',BLACK:'#7a5a48',INDIGENOUS:'#cf6a3c','MIXED-RACE':'#b98a5e',UNKNOWN:'#8b97a8'};
  var MALE_C = '#34a9e0', FEMALE_C = '#ef5b7b';

  var COORDS = {
    // North America
    'United States':{lng:-98.6,lat:39.8},'Canada':{lng:-106,lat:56},'Mexico':{lng:-102,lat:23.5},
    // Europe
    'United Kingdom':{lng:-2,lat:53},'France':{lng:2.4,lat:46.6},'Germany':{lng:10.4,lat:51},
    'Italy':{lng:12.6,lat:42.8},'Spain':{lng:-3.7,lat:40.2},'Netherlands':{lng:5.3,lat:52.1},
    'Belgium':{lng:4.5,lat:50.8},'Sweden':{lng:18.1,lat:59.3},'Denmark':{lng:10.0,lat:56.0},
    'Norway':{lng:10.7,lat:59.9},'Finland':{lng:25.7,lat:61.9},'Poland':{lng:19.1,lat:52.1},
    'Russia':{lng:37.6,lat:55.8},'Austria':{lng:14.5,lat:47.5},'Switzerland':{lng:8.3,lat:46.9},
    'Czechia':{lng:15.5,lat:49.8},'Hungary':{lng:19.0,lat:47.5},'Romania':{lng:24.9,lat:45.9},
    'Portugal':{lng:-8.2,lat:39.4},'Greece':{lng:21.8,lat:39.1},'Ireland':{lng:-8.2,lat:53.1},
    'Ukraine':{lng:30.5,lat:50.5},'Turkey':{lng:35.2,lat:38.9},'Israel':{lng:34.9,lat:31.5},
    'Serbia':{lng:21.0,lat:44.0},'Croatia':{lng:15.9,lat:45.1},'Bulgaria':{lng:25.5,lat:42.7},
    'Slovakia':{lng:19.3,lat:48.7},'Slovenia':{lng:14.8,lat:46.1},'Lithuania':{lng:23.9,lat:55.2},
    'Latvia':{lng:24.1,lat:56.9},'Estonia':{lng:24.7,lat:58.6},'Iceland':{lng:-18.2,lat:64.9},
    'Luxembourg':{lng:6.1,lat:49.8},'Moldova':{lng:28.4,lat:47.0},'Albania':{lng:20.2,lat:41.3},
    // Asia
    'Japan':{lng:138.3,lat:36.2},'South Korea':{lng:127.8,lat:36.5},'India':{lng:79,lat:22},
    'China':{lng:104.2,lat:35.9},'Hong Kong':{lng:114.2,lat:22.3},'Taiwan':{lng:120.9,lat:23.7},
    'Thailand':{lng:100.5,lat:13.8},'Vietnam':{lng:108.3,lat:14.1},'Indonesia':{lng:113.9,lat:-0.8},
    'Philippines':{lng:122.6,lat:12.9},'Malaysia':{lng:109.7,lat:4.2},'Singapore':{lng:103.8,lat:1.4},
    'Iran':{lng:53.7,lat:32.4},'Kazakhstan':{lng:66.9,lat:48.0},'Pakistan':{lng:69.3,lat:30.4},
    'Bangladesh':{lng:90.4,lat:23.7},'Sri Lanka':{lng:80.7,lat:7.9},'Cambodia':{lng:104.9,lat:12.6},
    'Mongolia':{lng:106.9,lat:47.9},'Nepal':{lng:84.1,lat:28.4},'Lebanon':{lng:35.5,lat:33.9},
    'Jordan':{lng:36.2,lat:31.0},'Saudi Arabia':{lng:45.1,lat:23.9},'United Arab Emirates':{lng:53.8,lat:23.4},
    'Georgia':{lng:43.4,lat:42.3},'Armenia':{lng:44.5,lat:40.2},'Azerbaijan':{lng:47.6,lat:40.1},
    'Uzbekistan':{lng:63.1,lat:41.4},'Tajikistan':{lng:71.3,lat:38.9},'Kyrgyzstan':{lng:74.6,lat:41.2},
    'Myanmar':{lng:96.1,lat:17.1},'Afghanistan':{lng:67.7,lat:33.9},
    // Latin America
    'Brazil':{lng:-51,lat:-12},'Argentina':{lng:-63,lat:-36},'Colombia':{lng:-74.1,lat:4.7},
    'Chile':{lng:-70.7,lat:-33.5},'Peru':{lng:-77.0,lat:-12.0},'Venezuela':{lng:-66.9,lat:10.5},
    'Bolivia':{lng:-64.7,lat:-17.1},'Ecuador':{lng:-78.1,lat:-1.8},'Paraguay':{lng:-58.4,lat:-23.4},
    'Uruguay':{lng:-56.2,lat:-32.5},'Cuba':{lng:-79.5,lat:21.5},'Puerto Rico':{lng:-66.5,lat:18.2},
    'Costa Rica':{lng:-84.1,lat:9.8},'Guatemala':{lng:-90.3,lat:15.8},'Dominican Republic':{lng:-70.2,lat:19.0},
    // Africa
    'South Africa':{lng:25.1,lat:-29.0},'Nigeria':{lng:8.7,lat:9.1},'Egypt':{lng:30.8,lat:26.8},
    'Kenya':{lng:37.9,lat:0.0},'Morocco':{lng:-7.1,lat:31.8},'Ethiopia':{lng:40.5,lat:9.1},
    'Ghana':{lng:-1.0,lat:7.9},'Tanzania':{lng:34.9,lat:-6.4},'Senegal':{lng:-14.5,lat:14.5},
    'Cameroon':{lng:12.4,lat:5.7},'Tunisia':{lng:9.6,lat:33.9},'Algeria':{lng:2.6,lat:28.0},
    "Côte d'Ivoire":{lng:-5.6,lat:7.5},'Democratic Republic of the Congo':{lng:23.7,lat:-4.0},
    // Oceania
    'Australia':{lng:133,lat:-25},'New Zealand':{lng:172.5,lat:-41.3}
  };

  // ISO 3166-1 numeric → country name (matches Oracle country names)
  var ISO_NUM = {
    4:'Afghanistan',8:'Albania',12:'Algeria',24:'Angola',32:'Argentina',36:'Australia',
    40:'Austria',50:'Bangladesh',56:'Belgium',64:'Bhutan',68:'Bolivia',76:'Brazil',
    100:'Bulgaria',104:'Myanmar',116:'Cambodia',120:'Cameroon',124:'Canada',152:'Chile',
    156:'China',170:'Colombia',178:'Republic of the Congo',
    180:'Democratic Republic of the Congo',188:'Costa Rica',191:'Croatia',192:'Cuba',
    196:'Cyprus',203:'Czechia',208:'Denmark',214:'Dominican Republic',218:'Ecuador',
    818:'Egypt',231:'Ethiopia',246:'Finland',250:'France',268:'Georgia',276:'Germany',
    288:'Ghana',300:'Greece',320:'Guatemala',332:'Haiti',344:'Hong Kong',348:'Hungary',
    356:'India',360:'Indonesia',364:'Iran',368:'Iraq',372:'Ireland',376:'Israel',
    380:'Italy',388:'Jamaica',392:'Japan',400:'Jordan',398:'Kazakhstan',404:'Kenya',
    408:'North Korea',410:'South Korea',417:'Kyrgyzstan',418:'Laos',422:'Lebanon',
    428:'Latvia',440:'Lithuania',442:'Luxembourg',450:'Madagascar',458:'Malaysia',
    484:'Mexico',496:'Mongolia',504:'Morocco',516:'Namibia',524:'Nepal',528:'Netherlands',
    554:'New Zealand',566:'Nigeria',578:'Norway',586:'Pakistan',591:'Panama',
    600:'Paraguay',604:'Peru',608:'Philippines',616:'Poland',620:'Portugal',634:'Qatar',
    642:'Romania',643:'Russia',646:'Rwanda',682:'Saudi Arabia',686:'Senegal',
    694:'Sierra Leone',702:'Singapore',703:'Slovakia',705:'Slovenia',706:'Somalia',
    710:'South Africa',724:'Spain',144:'Sri Lanka',752:'Sweden',756:'Switzerland',
    158:'Taiwan',762:'Tajikistan',764:'Thailand',788:'Tunisia',792:'Turkey',800:'Uganda',
    804:'Ukraine',784:'United Arab Emirates',826:'United Kingdom',840:'United States',
    858:'Uruguay',860:'Uzbekistan',704:'Vietnam',887:'Yemen',716:'Zimbabwe',
    384:"Côte d'Ivoire",233:'Estonia',862:'Venezuela',630:'Puerto Rico',
    312:'Guadeloupe',474:'Martinique',470:'Malta',492:'Monaco',480:'Mauritius'
  };

  // Nome do país (PAIS_ORIGEM, Ancine, PT-BR maiúsculo) → código ISO 3166-1 numérico
  // (para colorir o mapa mundi — o topojson do world-atlas usa esse código como id).
  var PAIS_ISO = {
    'AFEGANISTÃO':4,'ALBÂNIA':8,'ALEMANHA':276,'ANGOLA':24,'ARGENTINA':32,'ARGÉLIA':12,
    'ARUBA':533,'ARÁBIA SAUDITA':682,'AUSTRÁLIA':36,'AZERBAIJÃO':31,'BAHAMAS, ILHAS':44,
    'BAHREIN':48,'BANGLADESH':50,'BARBADOS':52,'BAREINE':48,'BELARUS, REPUBLICA DA':112,
    'BOLÍVIA':68,'BOTSUANA':72,'BRASIL':76,'BRUNEI':96,'BULGÁRIA':100,'BURKINA FASSO':854,
    'BUTÃO':64,'BÉLGICA':56,'BÓSNIA-HERZEGÓVINA':70,'CABO VERDE, REPUBLICA DE':132,
    'CAMARÕES':120,'CAMBOJA':116,'CANADÁ':124,'CAYMAN, ILHAS':136,'CAZAQUISTÃO':398,
    'CHADE':148,'CHILE':152,'CHINA, REPUBLICA POPULAR':156,'CHIPRE':196,'CINGAPURA':702,
    'COLÔMBIA':170,'CONGO':178,'CORÉIA DO NORTE':408,'CORÉIA DO SUL':410,
    'COSTA DO MARFIM':384,'COSTA RICA':188,'CROÁCIA (HRVATSKA)':191,'CUBA':192,
    'DINAMARCA':208,'EGITO':818,'EL SALVADOR':222,'EMIRADOS ÁRABES UNIDOS':784,
    'EQUADOR':218,'ESLOVÁQUIA':703,'ESLOVÊNIA':705,'ESPANHA':724,'ESTADOS UNIDOS':840,
    'ESTÔNIA':233,'ETIOPIA':231,'FIJI':242,'FILIPINAS':608,'FINLANDIA':246,
    'FORMOSA (TAIWAN)':158,'FRANCA':250,'GANA':288,'GEÓRGIA':268,'GRECIA':300,
    'GROELÂNDIA':304,'GUAM (TERRITÓRIO DOS ESTADOS UNIDOS)':316,'GUATEMALA':320,
    'GUINÉ EQUATORIAL':226,'GUINÉ-BISSAU':624,'GÂMBIA':270,'HAITI':332,'HONDURAS':340,
    'HONG KONG':344,'HUNGRIA, REPUBLICA DA':348,'ILHAS MARSHALL':584,
    'ILHAS VIRGENS (INGLATERRA)':92,'INDIA':356,'INDONESIA':360,'IRAQUE':368,
    'IRLANDA':372,'IRÃ':364,'ISLANDIA':352,'ISRAEL':376,'ITALIA':380,'IÊMEN':887,
    'JAMAICA':388,'JAPAO':392,'JORDANIA':400,'KÊNIA':404,'LETÔNIA':428,'LIBANO':422,
    'LIECHTENSTEIN':438,'LITUÂNIA':440,'LUXEMBURGO':442,'MACAU':446,
    'MACEDÔNIA (REPÚBLICA YUGOSLAVA)':807,'MADAGASCAR':450,'MALASIA':458,'MALI':466,
    'MALTA':470,'MARROCOS':504,'MAURITÂNIA':478,'MONGÓLIA':496,'MOÇAMBIQUE':508,
    'MÉXICO':484,'MÔNACO':492,'NAMÍBIA':516,'NEPAL':524,'NICARÁGUA':558,'NIGÉRIA':566,
    'NORUEGA':578,'NOVA ZELÂNDIA':554,'NÍGER':562,'PAISES BAIXOS (HOLANDA)':528,
    'PANAMÁ':591,'PAPUA-NOVA GUINÉ':598,'PAQUISTÃO':586,'PARAGUAI':600,'PERU':604,
    'POLINÉSIA FRANCESA':258,'POLÔNIA':616,'PORTO RICO':630,'PORTUGAL':620,'QATAR':634,
    'REINO UNIDO':826,'REPÚBLICA CENTRO-AFRICANA':140,'REPÚBLICA DEMOCRÁTICA DO CONGO':180,
    'REPÚBLICA DOMINICANA':214,'REPÚBLICA TCHECA':203,'ROMÊNIA':642,'RUANDA':646,
    'RÚSSIA':643,'SENEGAL':686,'SOMÁLIA':706,'SRI LANKA':144,'SUÉCIA':752,'SUÍÇA':756,
    'SÉRVIA':688,'SÍRIA':760,'TAILÂNDIA':764,'TANZÂNIA':834,
    'TERRITÓRIOS PALESTINOS OCUPADOS':275,'TOGO':768,'TRINIDAD E TOBAGO':780,
    'TUNÍSIA':788,'TURQUIA':792,'UCRÂNIA':804,'URUGUAI':858,'UZBEQUISTÃO':860,
    'VATICANO, EST. DA CIDADE DO':336,'VENEZUELA':862,'VIETNÃ':704,'ZÂMBIA':894,
    'ÁFRICA DO SUL':710,'ÁUSTRIA':40
  };

  var FILMS = []; // populated from /api/films on load

  /* Option data from country-data.js (fallback to film-derived) */
  function optionData() {
    var rows = window.CINEMAP_COUNTRY_ROWS;
    if (rows && rows.length) {
      return {
        conts: uniqSort(rows.map(function (r) { return r[1]; })),
        regs: uniqSort(rows.map(function (r) { return r[2]; })),
        countries: rows.map(function (r) { return r[0]; }).sort(function (a, b) { return a.localeCompare(b); })
      };
    }
    return {
      conts: uniqSort(FILMS.map(function (f) { return f.continent; })),
      regs: uniqSort(FILMS.map(function (f) { return f.region; })),
      countries: uniqSort(FILMS.map(function (f) { return f.country; }))
    };
  }
  function uniqSort(a) { return Array.from(new Set(a)).sort(); }

  /* ---------------- State ---------------- */
  var PAGE_SIZE = 50;
  var CHAT_PAGE_SIZE = 10;
  var state = {
    tab: 'bilheteria',
    open: { periodo: true, obra: false, salaexibicao: false, diretor: false, produtor: false, requerente: false },
    // Período
    anos: [], semanaInicio: '', semanaFim: '',
    // Obra
    cpbRoe: '', tituloBrasileiro: '', tituloOriginal: '', paisOrigem: [],
    // Sala de Exibição
    registroSala: '', grupoExibidor: [], municipioSala: [], ufSala: [],
    // Diretor
    nomeDiretor: '',
    // Produtor
    nomeProdutor: '',
    // Requerente
    cnpjRequerente: '', nomeRequerente: '', municipioRequerente: [], ufRequerente: [],
    // Aba Bilheteria (data/ancine/, via /api/ancine/bilheteria-resumo)
    // loadedQs guarda a query string (filtros) da última carga bem-sucedida —
    // ao trocar de aba ou re-renderizar, só refaz o fetch se os filtros
    // atuais forem diferentes do que já está carregado (ver render()/setTab()).
    bilheteriaResumo: null, bilheteriaGrafico: [], bilheteriaSemanal: [], bilheteriaLoadedQs: null,
    // Aba Países (data/ancine/, via /api/ancine/paises)
    paisesRows: [], paisesLoading: false, paisesLoadedQs: null,
    // Abas Diretores/Produtores/Requerente (data/ancine/, via PESSOA_TABS)
    pessoaTabs: {
      diretores:  { rows: [], loading: false, page: 0, sortKey: 'publicoTotal', sortDir: 'desc', loadedQs: null },
      produtores: { rows: [], loading: false, page: 0, sortKey: 'publicoTotal', sortDir: 'desc', loadedQs: null },
      requerente: { rows: [], loading: false, page: 0, sortKey: 'publicoTotal', sortDir: 'desc', loadedQs: null }
    },
    // Aba Filmes (data/ancine/, via /api/ancine/filmes)
    filmesRows: [], filmesLoading: false, filmesPage: 0, filmesLoadedQs: null,
    filmesSortKey: 'publico', filmesSortDir: 'desc',
    // Aba Exibidor (data/ancine/, via /api/ancine/salas)
    salasRows: [], salasLoading: false, salasPage: 0, salasLoadedQs: null,
    salasSortKey: 'publicoTotal', salasSortDir: 'desc',
    // Painel "Detalhes do Filme" (abas Filme/Diretor/Produtor/Requerente, via /api/ancine/filme-detalhe)
    detailAsideOpen: true,
    detailPessoa: null,        // { tab, nome } — quando veio de Diretor/Produtor/Requerente
    detailRelatedFilms: [], detailRelatedLoading: false, detailRelatedPage: 0,
    detailCodigo: null,        // CPB/ROE selecionado
    detailFilme: null, detailFilmeLoading: false,
    detailCrewTab: 'directors',
    // Painel "Detalhes da Sala" (aba Exibidor, via /api/ancine/sala-detalhe)
    detailSalaRegistro: null, detailSala: null, detailSalaLoading: false,
    // Chat com IA (aba "chat", via POST /api/chat/query) — mesmo painel lateral
    // usado por "Detalhes do Filme" vira a caixa de chat; resultado da última
    // pergunta respondida vai para o painel central (pane-chat)
    chat: { messages: [], input: '', loading: false, selected: -1, modelId: null, modelOptions: [], modelsLoading: false },
    sortKey: 'title', sortDir: 'asc',
    tablePage: 0,
    dirSortKey: 'count', dirSortDir: 'desc', dirPage: 0,
    wriSortKey: 'count', wriSortDir: 'desc', wriPage: 0
  };
  var OD = optionData();

  /* ---------------- Helpers ---------------- */
  function el(tag, props, children) {
    var e = document.createElement(tag);
    if (props) for (var k in props) {
      if (k === 'class') e.className = props[k];
      else if (k === 'html') e.innerHTML = props[k];
      else if (k === 'text') e.textContent = props[k];
      else if (k === 'style') e.style.cssText = props[k];
      else if (k.indexOf('on') === 0 && typeof props[k] === 'function') e.addEventListener(k.slice(2).toLowerCase(), props[k]);
      else if (props[k] != null) e.setAttribute(k, props[k]);
    }
    if (children != null) (Array.isArray(children) ? children : [children]).forEach(function (c) {
      if (c == null) return;
      e.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
    });
    return e;
  }
  function fmtMoney(m) { return m >= 1000 ? '$' + (m / 1000).toFixed(2) + 'B' : '$' + Math.round(m) + 'M'; }
  function fmtVotes(n) { if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M'; if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K'; return String(n); }
  function fmtInt(n) { return (n === null || n === undefined) ? '–' : n.toLocaleString('pt-BR'); }
  function colorOf(g) { return GENRE_COLORS[g] || '#9aa6b8'; }
  function $(id) { return document.getElementById(id); }
  function announce(message) {
    var status = $('app-status');
    if (status) status.textContent = message;
  }
  var errorBannerTimer = null;
  function showApiError() {
    var banner = $('error-banner');
    if (!banner) return;
    banner.textContent = 'Não foi possível atualizar os dados. Tente novamente.';
    banner.hidden = false;
    announce(banner.textContent);
    if (errorBannerTimer) clearTimeout(errorBannerTimer);
    errorBannerTimer = setTimeout(function () { banner.hidden = true; }, 6000);
  }
  function toTitleCase(s) {
    return (s || '').toLowerCase().replace(/(?:^|[\s\-\/])(\S)/g, function(m, c) { return m.slice(0, -1) + c.toUpperCase(); });
  }
  /* ---------------- Exportar CSV / copiar ---------------- */
  function csvEscape(v) {
    var s = v === null || v === undefined ? '' : String(v);
    return /[",\n;]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  function downloadCsv(filename, headers, rows) {
    var lines = [headers.map(csvEscape).join(',')].concat(
      rows.map(function (r) { return r.map(csvEscape).join(','); })
    );
    // BOM UTF-8 na frente — o Excel só detecta acentuação corretamente com ele
    var blob = new Blob(['﻿' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
    var url = URL.createObjectURL(blob);
    var a = el('a', { href: url, download: filename });
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }
  function exportButton(filename, headers, getRows) {
    return el('button', {
      class: 'export-csv-btn', title: 'Exportar como CSV',
      onclick: function () { downloadCsv(filename, headers, getRows()); }
    }, [
      el('span', {}, '⬇'), el('span', {}, 'Exportar CSV')
    ]);
  }
  function copyButton(label, getText) {
    var btn = el('button', { class: 'copy-btn' }, [el('span', {}, '⧉'), el('span', { class: 'copy-btn-label' }, label)]);
    btn.addEventListener('click', function () {
      var text = getText();
      var done = function () {
        var lbl = btn.querySelector('.copy-btn-label');
        var original = label;
        btn.classList.add('is-copied');
        if (lbl) lbl.textContent = 'Copiado!';
        setTimeout(function () { btn.classList.remove('is-copied'); if (lbl) lbl.textContent = original; }, 1500);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(done);
      } else {
        var ta = document.createElement('textarea');
        ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); } catch (e) {}
        document.body.removeChild(ta);
        done();
      }
    });
    return btn;
  }

  // Escapa HTML e converte a formatação leve que o modelo costuma usar
  // (**negrito**, quebras de linha) — a resposta do chat é texto do LLM,
  // não confiável o bastante para innerHTML direto.
  function mdToHtml(text) {
    var esc = String(text || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return esc
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
  }

  function chatModelLabel(id) {
    var found = state.chat.modelOptions.filter(function (m) { return m.id === id; })[0];
    return found ? found.label : id;
  }

  function loadPeriodoOptions() {
    window.dashboardApi.getJson('/api/ancine/periodo-options')
      .then(function (data) {
        PERIODO_OPTIONS = data || { anos: [], semanas: [] };
        render();
      })
      .catch(function () {});
  }

  function loadObraOptions() {
    window.dashboardApi.getJson('/api/ancine/obra-options')
      .then(function (data) {
        OBRA_OPTIONS = data || { paisOrigem: [] };
        render();
      })
      .catch(function () {});
  }

  function loadSalaOptions() {
    window.dashboardApi.getJson('/api/ancine/sala-options')
      .then(function (data) {
        SALA_OPTIONS = data || { combos: [] };
        render();
      })
      .catch(function () {});
  }

  // Opções em cascata do filtro Exibidor: Grupo Exibidor -> UF -> Município.
  // Selecionar um grupo restringe as UFs/municípios às daquele grupo; selecionar
  // uma UF restringe os municípios àquela UF.
  function salaGrupoOptions() {
    return uniqSort(SALA_OPTIONS.combos.map(function (c) { return c.grupoExibidor; }).filter(Boolean));
  }
  function salaCombosPorGrupo() {
    var grupos = state.grupoExibidor;
    if (!grupos.length) return SALA_OPTIONS.combos;
    return SALA_OPTIONS.combos.filter(function (c) { return c.grupoExibidor && grupos.indexOf(c.grupoExibidor) >= 0; });
  }
  function salaUfOptions() {
    return uniqSort(salaCombosPorGrupo().map(function (c) { return c.uf; }).filter(Boolean));
  }
  function salaMunicipioOptions() {
    var combos = salaCombosPorGrupo();
    var ufs = state.ufSala;
    if (ufs.length) combos = combos.filter(function (c) { return ufs.indexOf(c.uf) >= 0; });
    return uniqSort(combos.map(function (c) { return c.municipio; }).filter(Boolean));
  }

  /* ---------------- Aba Bilheteria (data/ancine/, via /api/ancine/bilheteria-resumo e -grafico) ---------------- */
  var _bilheteriaDebounce = null;
  var _bilheteriaReqSeq = 0;

  function scheduleLoadBilheteria() {
    if (_bilheteriaDebounce) clearTimeout(_bilheteriaDebounce);
    _bilheteriaDebounce = setTimeout(loadBilheteria, 350);
  }

  function loadBilheteria() {
    loadBilheteriaResumo();
    loadBilheteriaGrafico();
    loadBilheteriaSemanal();
  }

  function loadBilheteriaResumo() {
    var seq = ++_bilheteriaReqSeq;
    var qs = buildFilmesQueryString(); // mesmos filtros da sidebar
    window.dashboardApi.getLatest('box-office-summary', '/api/ancine/bilheteria-resumo' + (qs ? '?' + qs : ''))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (seq !== _bilheteriaReqSeq) return; // resposta de uma requisição antiga (superada)
        state.bilheteriaResumo = data;
        state.bilheteriaLoadedQs = qs;
        renderBilheteriaResumo();
      })
      .catch(function () {});
  }

  var _bilheteriaGraficoReqSeq = 0;

  function loadBilheteriaGrafico() {
    var seq = ++_bilheteriaGraficoReqSeq;
    var qs = buildFilmesQueryString();
    window.dashboardApi.getLatest('box-office-chart', '/api/ancine/bilheteria-grafico' + (qs ? '?' + qs : ''))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (seq !== _bilheteriaGraficoReqSeq) return;
        state.bilheteriaGrafico = (data && data.porAno) || [];
        state.bilheteriaLoadedQs = qs;
        renderBilheteriaCharts();
      })
      .catch(function () {});
  }

  var _bilheteriaSemanalReqSeq = 0;

  function loadBilheteriaSemanal() {
    var seq = ++_bilheteriaSemanalReqSeq;
    var qs = buildFilmesQueryString();
    window.dashboardApi.getLatest('box-office-weekly', '/api/ancine/bilheteria-semanal' + (qs ? '?' + qs : ''))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (seq !== _bilheteriaSemanalReqSeq) return;
        state.bilheteriaSemanal = (data && data.porSemana) || [];
        state.bilheteriaLoadedQs = qs;
        drawBilheteriaLineChart();
      })
      .catch(function () {});
  }

  function renderBilheteriaResumo() {
    var r = state.bilheteriaResumo;
    if (!r) return;
    $('bh-publico').textContent = fmtInt(r.publico);
    $('bh-dias').textContent = fmtInt(r.diasExibicao);
    $('bh-sessoes').textContent = fmtInt(r.sessoes);
    $('bh-titulos').textContent = fmtInt(r.titulosDistintos);
    $('bh-salas').textContent = fmtInt(r.salasDistintas);
  }

  /* ---------------- Bilheteria: gráficos (D3) ---------------- */
  var _bhResizeObservers = null;

  function renderBilheteriaCharts() {
    if (!window.d3 || !state.bilheteriaGrafico) return;
    drawBilheteriaBarChart();
    var totCpb = 0, totRoe = 0, sessCpb = 0, sessRoe = 0;
    state.bilheteriaGrafico.forEach(function (d) {
      totCpb += d.publicoCpb; totRoe += d.publicoRoe;
      sessCpb += d.sessoesCpb; sessRoe += d.sessoesRoe;
    });
    drawBilheteriaPie('bh-chart-pie-publico', 'bh-legend-pie-publico', 'bh-tooltip-pie-publico', totCpb, totRoe, 'Público');
    drawBilheteriaPie('bh-chart-pie-sessoes', 'bh-legend-pie-sessoes', 'bh-tooltip-pie-sessoes', sessCpb, sessRoe, 'Sessões');

    // redesenha ao redimensionar (uma vez só, observando os 3 painéis)
    if (!_bhResizeObservers) {
      _bhResizeObservers = new ResizeObserver(function () {
        drawBilheteriaBarChart();
        drawBilheteriaPie('bh-chart-pie-publico', 'bh-legend-pie-publico', 'bh-tooltip-pie-publico', totCpb, totRoe, 'Público');
        drawBilheteriaPie('bh-chart-pie-sessoes', 'bh-legend-pie-sessoes', 'bh-tooltip-pie-sessoes', sessCpb, sessRoe, 'Sessões');
        drawBilheteriaLineChart();
      });
      var row = $('bh-charts-row');
      if (row) _bhResizeObservers.observe(row);
    }
  }

  function chartLegend(elId, items) {
    var box = $(elId);
    if (!box) return;
    box.innerHTML = '';
    items.forEach(function (it) {
      box.appendChild(el('div', { class: 'chart-legend-item' }, [
        el('span', { class: 'chart-legend-dot', style: 'background:' + it.color }),
        it.label
      ]));
    });
  }

  function drawBilheteriaBarChart() {
    var svgEl = $('bh-chart-bar');
    if (!svgEl || !svgEl.parentElement) return;
    var data = state.bilheteriaGrafico;
    var box = svgEl.parentElement.getBoundingClientRect();
    var W = box.width, H = box.height;
    if (W <= 0 || H <= 0) return;

    var cpbColor = cssVar('--cpb-color'), roeColor = cssVar('--roe-color');
    chartLegend('bh-legend-bar', [{ color: cpbColor, label: 'CPB (brasileiras)' }, { color: roeColor, label: 'ROE (estrangeiras)' }]);

    var margin = { top: 14, right: 10, bottom: 22, left: 44 };
    var iw = Math.max(10, W - margin.left - margin.right);
    var ih = Math.max(10, H - margin.top - margin.bottom);

    var svg = d3.select(svgEl);
    svg.attr('viewBox', '0 0 ' + W + ' ' + H).attr('width', W).attr('height', H);
    svg.selectAll('*').remove();
    var g = svg.append('g').attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

    var x = d3.scaleBand().domain(data.map(function (d) { return d.ano; })).range([0, iw]).padding(0.32);
    var maxTotal = d3.max(data, function (d) { return d.publicoCpb + d.publicoRoe; }) || 1;
    var y = d3.scaleLinear().domain([0, maxTotal]).nice().range([ih, 0]);

    g.append('g').attr('class', 'chart-grid')
      .call(d3.axisLeft(y).ticks(5).tickSize(-iw).tickFormat(''));
    g.append('g').attr('class', 'chart-axis')
      .call(d3.axisLeft(y).ticks(5).tickFormat(fmtVotes));
    g.append('g').attr('class', 'chart-axis')
      .attr('transform', 'translate(0,' + ih + ')')
      .call(d3.axisBottom(x).tickSize(0))
      .call(function (sel) { sel.select('.domain').remove(); });

    var GAP = 2; // 2px surface gap entre os segmentos empilhados
    var tip = $('bh-tooltip-bar');
    var panel = svgEl.parentElement;

    function showTip(event, d) {
      var p = d3.pointer(event, panel);
      var total = d.publicoCpb + d.publicoRoe;
      tip.style.display = 'block';
      tip.style.left = p[0] + 'px'; tip.style.top = p[1] + 'px'; tip.style.transform = 'translate(14px,-50%)';
      tip.innerHTML = '<div class="tt-title">' + d.ano + '</div>' +
        '<div class="tt-row"><span>CPB</span><b>' + fmtInt(d.publicoCpb) + '</b></div>' +
        '<div class="tt-row"><span>ROE</span><b>' + fmtInt(d.publicoRoe) + '</b></div>' +
        '<div class="tt-top">Total: ' + fmtInt(total) + '</div>';
    }
    function hideTip() { tip.style.display = 'none'; }

    // Path de retângulo comum (cantos quadrados) e de retângulo com só o topo
    // arredondado (o "data-end" da pilha) — o extremo encostado na base (y=ih)
    // nunca arredonda, só o topo do segmento que está exposto no alto da barra.
    function rectPath(rx, ry, w, h) {
      if (h <= 0) return '';
      return 'M' + rx + ',' + ry + ' h' + w + ' v' + h + ' h' + (-w) + ' Z';
    }
    function roundedTopPath(rx, ry, w, h, r) {
      if (h <= 0) return '';
      r = Math.max(0, Math.min(r, w / 2, h));
      if (r === 0) return rectPath(rx, ry, w, h);
      return 'M' + rx + ',' + (ry + r) +
        ' Q' + rx + ',' + ry + ' ' + (rx + r) + ',' + ry +
        ' H' + (rx + w - r) +
        ' Q' + (rx + w) + ',' + ry + ' ' + (rx + w) + ',' + (ry + r) +
        ' V' + (ry + h) + ' H' + rx + ' Z';
    }

    var bars = g.selectAll('.bh-bar-group').data(data).join('g').attr('class', 'bh-bar-group')
      .attr('transform', function (d) { return 'translate(' + x(d.ano) + ',0)'; })
      .on('mousemove', showTip).on('mouseleave', hideTip);

    // CPB — segmento de baixo, encostado na base. Só ganha topo arredondado
    // quando é ele o extremo exposto da barra (ROE = 0).
    bars.append('path').attr('class', 'chart-mark')
      .attr('d', function (d) {
        var yTop = y(d.publicoCpb) - (d.publicoRoe > 0 ? GAP / 2 : 0);
        var h = ih - yTop;
        return d.publicoRoe > 0 ? rectPath(0, yTop, x.bandwidth(), h) : roundedTopPath(0, yTop, x.bandwidth(), h, 3);
      })
      .attr('fill', cpbColor);

    // ROE — segmento de cima, sempre o extremo exposto quando presente.
    bars.append('path').attr('class', 'chart-mark')
      .attr('d', function (d) {
        if (d.publicoRoe <= 0) return '';
        var yTop = y(d.publicoCpb + d.publicoRoe);
        var yBottom = y(d.publicoCpb) - GAP / 2;
        return roundedTopPath(0, yTop, x.bandwidth(), yBottom - yTop, 3);
      })
      .attr('fill', roeColor);
  }

  function drawBilheteriaPie(svgId, legendId, tooltipId, cpbVal, roeVal, seriesLabel) {
    var svgEl = $(svgId);
    if (!svgEl || !svgEl.parentElement) return;
    var box = svgEl.parentElement.getBoundingClientRect();
    var W = box.width, H = box.height;
    if (W <= 0 || H <= 0) return;

    var cpbColor = cssVar('--cpb-color'), roeColor = cssVar('--roe-color');
    var total = cpbVal + roeVal;
    var data = [
      { key: 'CPB', label: 'CPB (brasileiras)', value: cpbVal, color: cpbColor },
      { key: 'ROE', label: 'ROE (estrangeiras)', value: roeVal, color: roeColor }
    ];
    chartLegend(legendId, data.map(function (d) { return { color: d.color, label: d.label }; }));

    var radius = Math.min(W, H) / 2 - 8;
    var svg = d3.select(svgEl);
    svg.attr('viewBox', '0 0 ' + W + ' ' + H).attr('width', W).attr('height', H);
    svg.selectAll('*').remove();
    var g = svg.append('g').attr('transform', 'translate(' + W / 2 + ',' + H / 2 + ')');

    var pie = d3.pie().value(function (d) { return d.value; }).sort(null).padAngle(0.018);
    var arc = d3.arc().innerRadius(0).outerRadius(radius).cornerRadius(3);
    var arcs = pie(data);

    var tip = $(tooltipId);
    var panel = svgEl.parentElement;

    g.selectAll('path').data(arcs).join('path')
      .attr('class', 'chart-mark')
      .attr('d', arc)
      .attr('fill', function (d) { return d.data.color; })
      .on('mousemove', function (event, d) {
        var p = d3.pointer(event, panel);
        var pct = total ? (d.data.value / total * 100) : 0;
        tip.style.display = 'block';
        tip.style.left = (p[0] + W / 2) + 'px'; tip.style.top = (p[1] + H / 2) + 'px'; tip.style.transform = 'translate(14px,-50%)';
        tip.innerHTML = '<div class="tt-title">' + d.data.label + '</div>' +
          '<div class="tt-row"><span>' + seriesLabel + '</span><b>' + fmtInt(d.data.value) + '</b></div>' +
          '<div class="tt-top">' + pct.toFixed(1) + '% do total</div>';
      })
      .on('mouseleave', function () { tip.style.display = 'none'; });

    // rótulo de percentual direto na fatia (cabe bem com só 2 fatias)
    g.selectAll('.chart-slice-label').data(arcs).join('text')
      .attr('class', 'chart-slice-label')
      .attr('transform', function (d) { return 'translate(' + arc.centroid(d) + ')'; })
      .attr('fill', '#fff')
      .text(function (d) { return total ? Math.round(d.data.value / total * 100) + '%' : '0%'; });
  }

  var CAT_COLOR_COUNT = 8;
  function yearColor(index) { return cssVar('--cat-' + (index % CAT_COLOR_COUNT + 1)); }
  // Com mais de 8 anos simultâneos, a cor se repete — o 2º ciclo em diante
  // usa traço tracejado pra continuar distinguível (nunca só a cor repetida).
  function yearDash(index) { return Math.floor(index / CAT_COLOR_COUNT) === 0 ? null : '6 3'; }

  function drawBilheteriaLineChart() {
    var svgEl = $('bh-chart-linhas');
    if (!svgEl || !svgEl.parentElement || !window.d3) return;
    var box = svgEl.parentElement.getBoundingClientRect();
    var W = box.width, H = box.height;
    if (W <= 0 || H <= 0) return;

    // Agrupa por ano-cine — cada ano é uma linha, semanas 1..53 no eixo X.
    var byYear = {};
    state.bilheteriaSemanal.forEach(function (d) {
      (byYear[d.ano] || (byYear[d.ano] = [])).push(d);
    });
    var years = Object.keys(byYear).map(Number).sort(function (a, b) { return a - b; });
    var series = years.map(function (ano, i) {
      var pts = byYear[ano].slice().sort(function (a, b) { return a.semana - b.semana; });
      return { ano: ano, color: yearColor(i), dash: yearDash(i), pontos: pts };
    });

    chartLegend('bh-legend-linhas', series.map(function (s) { return { color: s.color, label: String(s.ano) }; }));
    // torna a legenda interativa (hover = destaca a linha do ano correspondente)
    var legendItems = document.querySelectorAll('#bh-legend-linhas .chart-legend-item');
    legendItems.forEach(function (item, i) {
      item.classList.add('is-clickable');
      item.addEventListener('mouseenter', function () { highlightYear(series[i].ano); });
      item.addEventListener('mouseleave', function () { highlightYear(null); });
    });

    var margin = { top: 14, right: 16, bottom: 26, left: 48 };
    var iw = Math.max(10, W - margin.left - margin.right);
    var ih = Math.max(10, H - margin.top - margin.bottom);

    var svg = d3.select(svgEl);
    svg.attr('viewBox', '0 0 ' + W + ' ' + H).attr('width', W).attr('height', H);
    svg.selectAll('*').remove();
    var g = svg.append('g').attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

    var x = d3.scaleLinear().domain([1, 53]).range([0, iw]);
    var maxPublico = d3.max(state.bilheteriaSemanal, function (d) { return d.publico; }) || 1;
    var y = d3.scaleLinear().domain([0, maxPublico]).nice().range([ih, 0]);

    g.append('g').attr('class', 'chart-grid')
      .call(d3.axisLeft(y).ticks(5).tickSize(-iw).tickFormat(''));
    g.append('g').attr('class', 'chart-axis')
      .call(d3.axisLeft(y).ticks(5).tickFormat(fmtVotes));
    g.append('g').attr('class', 'chart-axis')
      .attr('transform', 'translate(0,' + ih + ')')
      .call(d3.axisBottom(x).ticks(13).tickFormat(d3.format('d')));

    var line = d3.line()
      .x(function (d) { return x(d.semana); })
      .y(function (d) { return y(d.publico); });

    var linesG = g.append('g');
    linesG.selectAll('.chart-line').data(series).join('path')
      .attr('class', 'chart-line')
      .attr('data-ano', function (d) { return d.ano; })
      .attr('d', function (d) { return line(d.pontos); })
      .attr('stroke', function (d) { return d.color; })
      .attr('stroke-dasharray', function (d) { return d.dash; });

    // hit-path mais larga (10px) para facilitar o hover na linha fina
    var hitG = g.append('g');
    hitG.selectAll('.chart-line-hit').data(series).join('path')
      .attr('class', 'chart-line-hit')
      .attr('d', function (d) { return line(d.pontos); })
      .on('mouseenter', function (event, d) { highlightYear(d.ano); })
      .on('mouseleave', function () { highlightYear(null); });

    function highlightYear(ano) {
      linesG.selectAll('.chart-line').classed('is-dim', function (d) { return ano != null && d.ano !== ano; });
      document.querySelectorAll('#bh-legend-linhas .chart-legend-item').forEach(function (item, i) {
        item.classList.toggle('is-dim', ano != null && series[i].ano !== ano);
      });
    }

    // Crosshair + tooltip: acompanha o mouse, acha a semana mais próxima e
    // lista o público de todos os anos naquela semana (ordenado, maior primeiro).
    var crosshair = g.append('line').attr('class', 'chart-axis')
      .attr('y1', 0).attr('y2', ih).style('display', 'none');
    var tip = $('bh-tooltip-linhas');
    var panel = svgEl.parentElement;

    svg.append('rect')
      .attr('x', margin.left).attr('y', margin.top).attr('width', iw).attr('height', ih)
      .attr('fill', 'transparent')
      .on('mousemove', function (event) {
        var px = d3.pointer(event, g.node())[0];
        var semana = Math.max(1, Math.min(53, Math.round(x.invert(px))));
        crosshair.attr('x1', x(semana)).attr('x2', x(semana)).style('display', null);

        var rows = series.map(function (s) {
          var pt = s.pontos.filter(function (p) { return p.semana === semana; })[0];
          return { ano: s.ano, color: s.color, publico: pt ? pt.publico : 0 };
        }).filter(function (r) { return r.publico > 0; })
          .sort(function (a, b) { return b.publico - a.publico; });

        var p = d3.pointer(event, panel);
        tip.style.display = 'block';
        tip.style.left = p[0] + 'px'; tip.style.top = p[1] + 'px'; tip.style.transform = 'translate(14px,-50%)';
        tip.innerHTML = '<div class="tt-title">Semana ' + semana + '</div>' +
          rows.map(function (r) {
            return '<div class="tt-row"><span><span class="chart-legend-dot" style="background:' + r.color +
              ';display:inline-block;margin-right:5px;"></span>' + r.ano + '</span><b>' + fmtInt(r.publico) + '</b></div>';
          }).join('');
      })
      .on('mouseleave', function () {
        crosshair.style('display', 'none');
        tip.style.display = 'none';
      });
  }

  /* ---------------- Aba Países (data/ancine/, via /api/ancine/paises) ---------------- */
  var _paisesDebounce = null;
  var _paisesReqSeq = 0;
  var _paisesResizeObserver = null;

  function scheduleLoadPaises() {
    if (_paisesDebounce) clearTimeout(_paisesDebounce);
    _paisesDebounce = setTimeout(loadPaises, 350);
  }

  function loadPaises() {
    var seq = ++_paisesReqSeq;
    state.paisesLoading = true;
    var qs = buildFilmesQueryString();
    fetch('/api/ancine/paises' + (qs ? '?' + qs : ''))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (seq !== _paisesReqSeq) return; // resposta de uma requisição antiga (superada)
        state.paisesRows = data || [];
        state.paisesLoading = false;
        state.paisesLoadedQs = qs;
        renderPaisesPane();
      })
      .catch(function () {
        if (seq !== _paisesReqSeq) return;
        state.paisesLoading = false;
      });
  }

  function ensureWorldAtlas(cb) {
    if (_world) { cb(); return; }
    if (_worldLoading) { setTimeout(function () { ensureWorldAtlas(cb); }, 120); return; }
    _worldLoading = true;
    window.dashboardApi.getJson('/static/vendor/countries-110m.json')
      .then(function (r) { return r.json(); })
      .then(function (topo) {
        _world = window.topojson.feature(topo, topo.objects.countries).features;
        cb();
      })
      .catch(function () {});
  }

  function paisTipFn(entry) {
    return '<div class="tt-title">' + toTitleCase(entry.nome) + '</div>' +
      '<div class="tt-row"><span>Público</span><b>' + fmtInt(entry.publicoTotal) + '</b></div>' +
      '<div class="tt-row"><span>Sessões</span><b>' + fmtInt(entry.sessoes) + '</b></div>' +
      '<div class="tt-row"><span>Títulos</span><b>' + fmtInt(entry.qtdTitulos) + '</b></div>';
  }

  function drawPaisMap(holderId, tooltipId, valueKey, maxLabel, colorVar, faintVar) {
    var holder = $(holderId);
    if (!holder || !window.d3 || !_world) return;
    var w = holder.clientWidth, h = holder.clientHeight;
    if (!w || !h) return;
    var d3 = window.d3;
    var accent      = cssVar(colorVar) || '#efa838';
    var accentFaint = cssVar(faintVar) || 'rgba(239,168,56,.1)';
    var sphere    = cssVar('--map-sphere'), sphereS = cssVar('--map-sphere-s');
    var grid      = cssVar('--map-grid'),   empty   = cssVar('--map-empty');
    var border    = cssVar('--map-border'), labelClr = cssVar('--map-label'), legendClr = cssVar('--map-legend');

    holder.innerHTML = '';
    var svg = d3.select(holder).append('svg').attr('width', w).attr('height', h).attr('viewBox', '0 0 ' + w + ' ' + h);
    var projection = d3.geoNaturalEarth1().fitExtent([[14, 14], [w - 14, h - 14]], { type: 'Sphere' });
    var path = d3.geoPath(projection);

    svg.append('path').attr('d', path({ type: 'Sphere' })).attr('fill', sphere).attr('stroke', sphereS).attr('stroke-width', 0.6);
    svg.append('path').attr('d', path(d3.geoGraticule10())).attr('fill', 'none').attr('stroke', grid).attr('stroke-width', 0.5);

    var data = state.paisesRows;
    var byIso = {};
    data.forEach(function (r) {
      var iso = PAIS_ISO[r.nome];
      if (iso != null) byIso[iso] = r;
    });

    var max = d3.max(data, function (r) { return r[valueKey]; }) || 1;
    var colorScale = d3.scaleSequentialSqrt().domain([0, max]).interpolator(d3.interpolate(accentFaint, accent));

    var tip = $(tooltipId);

    svg.append('g').selectAll('path')
      .data(_world)
      .join('path')
      .attr('d', path)
      .attr('fill', function (d) {
        var entry = byIso[+d.id];
        return entry ? colorScale(entry[valueKey]) : empty;
      })
      .attr('stroke', border)
      .attr('stroke-width', 0.4)
      .style('cursor', function (d) { return byIso[+d.id] ? 'pointer' : 'default'; })
      .on('mousemove', function (event, d) {
        var entry = byIso[+d.id];
        if (!entry) { tip.style.display = 'none'; return; }
        var p = d3.pointer(event, holder);
        tip.style.display = 'block';
        tip.style.left = p[0] + 'px'; tip.style.top = p[1] + 'px'; tip.style.transform = 'translate(14px,-50%)';
        tip.innerHTML = paisTipFn(entry);
      })
      .on('mouseleave', function () { tip.style.display = 'none'; });

    // Rótulos dos continentes
    var labels = [['NORTH AMERICA', -100, 47], ['SOUTH AMERICA', -58, -13], ['EUROPE', 13, 52], ['AFRICA', 20, 4], ['ASIA', 95, 46], ['OCEANIA', 134, -26]];
    svg.append('g').selectAll('text').data(labels).join('text')
      .attr('transform', function (d) { var p = projection([d[1], d[2]]); return 'translate(' + p[0] + ',' + p[1] + ')'; })
      .text(function (d) { return d[0]; }).attr('text-anchor', 'middle').attr('dy', '0.3em')
      .attr('fill', labelClr).attr('font-size', 10).attr('letter-spacing', 2.5)
      .attr('font-family', 'JetBrains Mono, monospace').style('pointer-events', 'none');

    // Legenda em gradiente (0 até o máximo do valor mapeado)
    var gradId = 'choro-grad-' + holderId;
    var lw = 120, lh = 8, lx = w - lw - 16, ly = h - 24;
    var defs = svg.append('defs');
    var grad = defs.append('linearGradient').attr('id', gradId);
    grad.append('stop').attr('offset', '0%').attr('stop-color', accentFaint);
    grad.append('stop').attr('offset', '100%').attr('stop-color', accent);
    var lg = svg.append('g').attr('transform', 'translate(' + lx + ',' + ly + ')');
    lg.append('rect').attr('width', lw).attr('height', lh).attr('rx', 2).attr('fill', 'url(#' + gradId + ')').attr('opacity', 0.9);
    lg.append('text').attr('x', 0).attr('y', lh + 11).attr('fill', legendClr).attr('font-size', 9).attr('font-family', 'JetBrains Mono, monospace').text('0');
    lg.append('text').attr('x', lw).attr('y', lh + 11).attr('text-anchor', 'end').attr('fill', legendClr).attr('font-size', 9).attr('font-family', 'JetBrains Mono, monospace').text(fmtVotes(max) + ' ' + maxLabel);
  }

  function drawPaisesMaps() {
    ensureWorldAtlas(function () {
      drawPaisMap('paises-map-holder-publico', 'paises-tooltip-publico', 'publicoTotal', 'público', '--map-green',  '--map-green-faint');
      drawPaisMap('paises-map-holder-sessoes', 'paises-tooltip-sessoes', 'sessoes',      'sessões', '--map-purple', '--map-purple-faint');
    });
  }

  function renderPaisesBars() {
    var wrap = $('paises-bars-row');
    if (!wrap || !state.paisesRows.length) return;
    wrap.innerHTML = '';
    var rows = state.paisesRows;

    function top20(key, color) {
      return rows.slice()
        .sort(function (a, b) { return (b[key] || 0) - (a[key] || 0); })
        .slice(0, 20)
        .map(function (r) { return { label: toTitleCase(r.nome), n: r[key] || 0, color: color }; });
    }

    wrap.appendChild(hbarChart('TOP 20 PAÍS × PÚBLICO', top20('publicoTotal', cssVar('--map-green')), fmtInt));
    wrap.appendChild(hbarChart('TOP 20 PAÍS × SESSÕES', top20('sessoes', cssVar('--map-purple')), fmtInt));
    wrap.appendChild(hbarChart('TOP 20 PAÍS × TÍTULOS', top20('qtdTitulos', cssVar('--accent')), fmtInt));
  }

  function renderPaisesPane() {
    if (!window.d3 || !window.topojson) return;
    drawPaisesMaps();
    renderPaisesBars();

    if (!_paisesResizeObserver) {
      _paisesResizeObserver = new ResizeObserver(function () { drawPaisesMaps(); });
      var row = $('paises-map-row');
      if (row) _paisesResizeObserver.observe(row);
    }
  }

  /* ---------------- Abas Diretores/Produtores/Requerente (data/ancine/) ---------------- */
  var PESSOA_TABS = [
    { tab: 'diretores',  pane: 'pane-diretores',  endpoint: '/api/ancine/diretores',    label: 'Diretor' },
    { tab: 'produtores', pane: 'pane-produtores', endpoint: '/api/ancine/produtores',   label: 'Produtor' },
    { tab: 'requerente', pane: 'pane-requerente', endpoint: '/api/ancine/requerentes',  label: 'Requerente' }
  ];

  function pessoaColumns(label) {
    return [
      { key: 'nome',                label: label },
      { key: 'qtdTitulos',           label: 'Qtd. Títulos',            right: true },
      { key: 'publicoTotal',         label: 'Público Total',           right: true },
      { key: 'sessoes',              label: 'Sessões',                 right: true },
      { key: 'diasExibicao',         label: 'Dias Exibição',           right: true },
      { key: 'publicoMedioTitulo',   label: 'Média Público/Título',    right: true },
      { key: 'sessoesMediaTitulo',   label: 'Média Sessão/Título',     right: true }
    ];
  }

  var _pessoaDebounce = {};
  var _pessoaReqSeq = {};

  function schedulePessoaLoad(cfg) {
    if (_pessoaDebounce[cfg.tab]) clearTimeout(_pessoaDebounce[cfg.tab]);
    _pessoaDebounce[cfg.tab] = setTimeout(function () { loadPessoaTab(cfg); }, 350);
  }

  function loadPessoaTab(cfg) {
    var seq = (_pessoaReqSeq[cfg.tab] || 0) + 1;
    _pessoaReqSeq[cfg.tab] = seq;
    var st = state.pessoaTabs[cfg.tab];
    st.loading = true;
    renderPessoaPane(cfg);
    var qs = buildFilmesQueryString(); // mesmos filtros da sidebar
    window.dashboardApi.getLatest('people-' + cfg.tab, cfg.endpoint + (qs ? '?' + qs : ''))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (seq !== _pessoaReqSeq[cfg.tab]) return; // resposta de uma requisição antiga (superada)
        st.rows = data || [];
        st.loading = false;
        st.page = 0;
        st.loadedQs = qs;
        renderPessoaPane(cfg);
      })
      .catch(function () {
        if (seq !== _pessoaReqSeq[cfg.tab]) return;
        st.loading = false;
        renderPessoaPane(cfg);
      });
  }

  function renderPessoaPane(cfg) {
    var pane = $(cfg.pane);
    if (!pane) return;
    var st = state.pessoaTabs[cfg.tab];
    var columns = pessoaColumns(cfg.label);

    var wrap = pane.querySelector('.table-wrap');
    if (!wrap) {
      pane.innerHTML = '';
      wrap = el('div', { class: 'table-wrap' }, [
        el('div', { class: 'thead', id: cfg.tab + '-thead' }),
        el('div', { id: cfg.tab + '-tbody' }),
        el('div', { class: 'tpager', id: cfg.tab + '-tpager' })
      ]);
      pane.appendChild(wrap);
    }

    if (st.loading) {
      $(cfg.tab + '-thead').innerHTML = '';
      $(cfg.tab + '-tpager').innerHTML = '';
      var body0 = $(cfg.tab + '-tbody'); body0.innerHTML = '';
      body0.appendChild(el('div', { class: 'empty-row' }, 'Carregando…'));
      return;
    }

    var dir = st.sortDir === 'asc' ? 1 : -1;
    var sorted = st.rows.slice().sort(function (a, b) {
      var av = a[st.sortKey], bv = b[st.sortKey];
      if (av === null || av === undefined) av = typeof bv === 'string' ? '' : -Infinity;
      if (bv === null || bv === undefined) bv = typeof av === 'string' ? '' : -Infinity;
      if (typeof av === 'string') return av.localeCompare(bv) * dir;
      return (av - bv) * dir;
    });

    var total = sorted.length;
    var totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    st.page = Math.min(st.page, totalPages - 1);
    var start = st.page * PAGE_SIZE;
    var page = sorted.slice(start, start + PAGE_SIZE);

    var head = $(cfg.tab + '-thead'); head.innerHTML = '';
    columns.forEach(function (c) {
      var active = st.sortKey === c.key;
      var arrow = active ? (st.sortDir === 'asc' ? ' ↑' : ' ↓') : '';
      head.appendChild(el('div', {
        class: 'th' + (c.right ? ' right' : '') + (active ? ' active' : ''),
        onclick: function () {
          if (st.sortKey === c.key) st.sortDir = st.sortDir === 'desc' ? 'asc' : 'desc';
          else { st.sortKey = c.key; st.sortDir = c.right ? 'desc' : 'asc'; }
          st.page = 0;
          renderPessoaPane(cfg);
        }
      }, c.label + arrow));
    });

    var body = $(cfg.tab + '-tbody'); body.innerHTML = '';
    if (!page.length) {
      body.appendChild(el('div', { class: 'empty-row' }, 'Nenhum registro encontrado para os filtros atuais.'));
    } else {
      var clickavel = cfg.tab === 'diretores' || cfg.tab === 'produtores' || cfg.tab === 'requerente';
      page.forEach(function (r) {
        var active = clickavel && state.detailPessoa && state.detailPessoa.tab === cfg.tab && state.detailPessoa.nome === r.nome;
        body.appendChild(el('div', {
          class: 'trow' + (clickavel ? ' clickable' : '') + (active ? ' trow-active' : ''),
          onclick: clickavel ? function () { selectPessoaRelacionada(cfg.tab, r.nome); } : null
        }, [
          el('div', { class: 'cell b' }, r.nome || '–'),
          el('div', { class: 'cell mono right' }, fmtInt(r.qtdTitulos)),
          el('div', { class: 'cell mono right' }, fmtInt(r.publicoTotal)),
          el('div', { class: 'cell mono right' }, fmtInt(r.sessoes)),
          el('div', { class: 'cell mono right' }, fmtInt(r.diasExibicao)),
          el('div', { class: 'cell mono right' }, r.publicoMedioTitulo != null ? fmtInt(Math.round(r.publicoMedioTitulo)) : '–'),
          el('div', { class: 'cell mono right' }, r.sessoesMediaTitulo != null ? fmtInt(Math.round(r.sessoesMediaTitulo)) : '–')
        ]));
      });
    }

    var pager = $(cfg.tab + '-tpager'); pager.innerHTML = '';
    var from = total ? start + 1 : 0;
    var to = Math.min(start + PAGE_SIZE, total);
    var nav = el('div', { class: 'tpager-nav' }, [
      el('button', {
        class: 'pager-btn' + (st.page === 0 ? ' disabled' : ''),
        onclick: function () { if (st.page > 0) { st.page--; renderPessoaPane(cfg); } }
      }, '<'),
      el('span', { class: 'pager-info' }, from + '–' + to + ' / ' + total + ' registros'),
      el('button', {
        class: 'pager-btn' + (st.page >= totalPages - 1 ? ' disabled' : ''),
        onclick: function () { if (st.page < totalPages - 1) { st.page++; renderPessoaPane(cfg); } }
      }, '>')
    ]);
    pager.appendChild(nav);
    pager.appendChild(exportButton(cfg.tab + '.csv', columns.map(function (c) { return c.label; }), function () {
      return sorted.map(function (r) { return columns.map(function (c) { return r[c.key]; }); });
    }));
  }

  /* ---------------- Aba Filmes (data/ancine/, via /api/ancine/filmes) ---------------- */
  var FILMES_COLUMNS = [
    { key: 'codigo',               label: 'CPB/ROE' },
    { key: 'tituloBrasil',         label: 'Título Brasil' },
    { key: 'tituloOriginal',       label: 'Título Original' },
    { key: 'paisProdutor',         label: 'País Produtor' },
    { key: 'ano1aExibicao',        label: 'Ano 1ª Exibição',        right: true },
    { key: 'publico',              label: 'Público',                right: true },
    { key: 'sessoesRealizadas',    label: 'Sessões Realizadas',     right: true },
    { key: 'diasExibicao',         label: 'Dias Exibição',          right: true },
    { key: 'publicoMedioSessao',   label: 'Público Médio/Sessão',   right: true },
    { key: 'maxSalasOcupadas',     label: 'Máx. Salas Ocupadas',    right: true },
    { key: 'maxComplexosOcupados', label: 'Máx. Complexos Ocupados', right: true }
  ];

  function buildFilmesQueryString() {
    var parts = [];
    function add(key, val) { if (val) parts.push(key + '=' + encodeURIComponent(val)); }
    function addAll(key, arr) { (arr || []).forEach(function (v) { parts.push(key + '=' + encodeURIComponent(v)); }); }
    addAll('anos', state.anos);
    add('semanaInicio', state.semanaInicio);
    add('semanaFim', state.semanaFim);
    add('cpbRoe', state.cpbRoe);
    add('tituloBrasileiro', state.tituloBrasileiro);
    add('tituloOriginal', state.tituloOriginal);
    addAll('paisOrigem', state.paisOrigem);
    add('registroSala', state.registroSala);
    addAll('grupoExibidor', state.grupoExibidor);
    addAll('municipioSala', state.municipioSala);
    addAll('ufSala', state.ufSala);
    add('nomeDiretor', state.nomeDiretor);
    add('nomeProdutor', state.nomeProdutor);
    add('cnpjRequerente', state.cnpjRequerente);
    add('nomeRequerente', state.nomeRequerente);
    addAll('municipioRequerente', state.municipioRequerente);
    addAll('ufRequerente', state.ufRequerente);
    return parts.join('&');
  }

  var URL_ARRAY_FILTERS = ['anos', 'paisOrigem', 'grupoExibidor', 'municipioSala', 'ufSala', 'municipioRequerente', 'ufRequerente'];
  var URL_TEXT_FILTERS = ['semanaInicio', 'semanaFim', 'cpbRoe', 'tituloBrasileiro', 'tituloOriginal', 'registroSala', 'nomeDiretor', 'nomeProdutor', 'cnpjRequerente', 'nomeRequerente'];
  var VALID_TABS = ['bilheteria', 'filmes', 'diretores', 'produtores', 'requerente', 'salaexibicao', 'paises', 'chat'];

  function restoreStateFromUrl() {
    var params = new URLSearchParams(window.location.search);
    URL_ARRAY_FILTERS.forEach(function (key) {
      var values = params.getAll(key);
      state[key] = key === 'anos' ? values.map(Number).filter(Number.isFinite) : values;
    });
    URL_TEXT_FILTERS.forEach(function (key) {
      if (params.has(key)) state[key] = params.get(key) || '';
    });
    var tab = params.get('tab');
    if (VALID_TABS.indexOf(tab) >= 0) state.tab = tab;
  }

  function syncStateToUrl() {
    var query = buildFilmesQueryString();
    var params = new URLSearchParams(query);
    if (state.tab !== 'bilheteria') params.set('tab', state.tab);
    var next = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
    if (next !== window.location.pathname + window.location.search) {
      window.history.replaceState(null, '', next);
    }
  }

  var _filmesDebounce = null;
  var _filmesReqSeq = 0;

  function scheduleLoadFilmes() {
    if (_filmesDebounce) clearTimeout(_filmesDebounce);
    _filmesDebounce = setTimeout(loadFilmes, 350);
  }

  function loadFilmes() {
    var seq = ++_filmesReqSeq;
    state.filmesLoading = true;
    renderFilmesPane();
    var qs = buildFilmesQueryString();
    window.dashboardApi.getLatest('films', '/api/ancine/filmes' + (qs ? '?' + qs : ''))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (seq !== _filmesReqSeq) return; // resposta de uma requisição antiga (superada)
        state.filmesRows = data || [];
        state.filmesLoading = false;
        state.filmesPage = 0;
        state.filmesLoadedQs = qs;
        renderFilmesPane();
      })
      .catch(function () {
        if (seq !== _filmesReqSeq) return;
        state.filmesLoading = false;
        renderFilmesPane();
      });
  }

  function renderFilmesPane() {
    var pane = $('pane-filmes');
    if (!pane) return;

    var wrap = pane.querySelector('.table-wrap');
    if (!wrap) {
      pane.innerHTML = '';
      wrap = el('div', { class: 'table-wrap' }, [
        el('div', { class: 'thead', id: 'filmes-thead' }),
        el('div', { id: 'filmes-tbody' }),
        el('div', { class: 'tpager', id: 'filmes-tpager' })
      ]);
      pane.appendChild(wrap);
    }

    if (state.filmesLoading) {
      $('filmes-thead').innerHTML = '';
      $('filmes-tpager').innerHTML = '';
      var body0 = $('filmes-tbody'); body0.innerHTML = '';
      body0.appendChild(el('div', { class: 'empty-row' }, 'Carregando…'));
      return;
    }

    var dir = state.filmesSortDir === 'asc' ? 1 : -1;
    var sorted = state.filmesRows.slice().sort(function (a, b) {
      var av = a[state.filmesSortKey], bv = b[state.filmesSortKey];
      if (av === null || av === undefined) av = typeof bv === 'string' ? '' : -Infinity;
      if (bv === null || bv === undefined) bv = typeof av === 'string' ? '' : -Infinity;
      if (typeof av === 'string') return av.localeCompare(bv) * dir;
      return (av - bv) * dir;
    });

    var total = sorted.length;
    var totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    state.filmesPage = Math.min(state.filmesPage, totalPages - 1);
    var start = state.filmesPage * PAGE_SIZE;
    var page = sorted.slice(start, start + PAGE_SIZE);

    var head = $('filmes-thead'); head.innerHTML = '';
    FILMES_COLUMNS.forEach(function (c) {
      var active = state.filmesSortKey === c.key;
      var arrow = active ? (state.filmesSortDir === 'asc' ? ' ↑' : ' ↓') : '';
      head.appendChild(el('div', {
        class: 'th' + (c.right ? ' right' : '') + (active ? ' active' : ''),
        onclick: function () {
          if (state.filmesSortKey === c.key) state.filmesSortDir = state.filmesSortDir === 'desc' ? 'asc' : 'desc';
          else { state.filmesSortKey = c.key; state.filmesSortDir = c.right ? 'desc' : 'asc'; }
          state.filmesPage = 0;
          renderFilmesPane();
        }
      }, c.label + arrow));
    });

    var body = $('filmes-tbody'); body.innerHTML = '';
    if (!page.length) {
      body.appendChild(el('div', { class: 'empty-row' }, 'Nenhum filme encontrado para os filtros atuais.'));
    } else {
      page.forEach(function (r) {
        var active = state.detailCodigo === r.codigo && !state.detailPessoa;
        body.appendChild(el('div', {
          class: 'trow clickable' + (active ? ' trow-active' : ''),
          onclick: function () { selectFilmeDetalhe(r.codigo); }
        }, [
          el('div', { class: 'cell mono' }, r.codigo),
          el('div', { class: 'cell b' }, r.tituloBrasil || '–'),
          el('div', { class: 'cell muted' }, r.tituloOriginal || '–'),
          el('div', { class: 'cell muted' }, r.paisProdutor || '–'),
          el('div', { class: 'cell mono right' }, r.ano1aExibicao || '–'),
          el('div', { class: 'cell mono right' }, fmtInt(r.publico)),
          el('div', { class: 'cell mono right' }, fmtInt(r.sessoesRealizadas)),
          el('div', { class: 'cell mono right' }, fmtInt(r.diasExibicao)),
          el('div', { class: 'cell mono right' }, r.publicoMedioSessao != null ? r.publicoMedioSessao.toFixed(1) : '–'),
          el('div', { class: 'cell mono right' }, fmtInt(r.maxSalasOcupadas)),
          el('div', { class: 'cell mono right' }, fmtInt(r.maxComplexosOcupados))
        ]));
      });
    }

    var pager = $('filmes-tpager'); pager.innerHTML = '';
    var from = total ? start + 1 : 0;
    var to = Math.min(start + PAGE_SIZE, total);
    var nav = el('div', { class: 'tpager-nav' }, [
      el('button', {
        class: 'pager-btn' + (state.filmesPage === 0 ? ' disabled' : ''),
        onclick: function () { if (state.filmesPage > 0) { state.filmesPage--; renderFilmesPane(); } }
      }, '<'),
      el('span', { class: 'pager-info' }, from + '–' + to + ' / ' + total + ' filmes'),
      el('button', {
        class: 'pager-btn' + (state.filmesPage >= totalPages - 1 ? ' disabled' : ''),
        onclick: function () { if (state.filmesPage < totalPages - 1) { state.filmesPage++; renderFilmesPane(); } }
      }, '>')
    ]);
    pager.appendChild(nav);
    pager.appendChild(exportButton('filmes.csv', FILMES_COLUMNS.map(function (c) { return c.label; }), function () {
      return sorted.map(function (r) { return FILMES_COLUMNS.map(function (c) { return r[c.key]; }); });
    }));
  }

  /* ---------------- Aba Exibidor (data/ancine/, via /api/ancine/salas) ---------------- */
  var SALAS_COLUMNS = [
    { key: 'exibidor',           label: 'Exibidor' },
    { key: 'complexo',           label: 'Complexo' },
    { key: 'sala',               label: 'Sala' },
    { key: 'qtdTitulos',         label: 'Qtd. Títulos',          right: true },
    { key: 'publicoTotal',       label: 'Público Total',         right: true },
    { key: 'sessoes',            label: 'Sessões',               right: true },
    { key: 'publicoMedioSessao', label: 'Média Público/Sessão',  right: true }
  ];

  var _salasDebounce = null;
  var _salasReqSeq = 0;

  function scheduleLoadSalas() {
    if (_salasDebounce) clearTimeout(_salasDebounce);
    _salasDebounce = setTimeout(loadSalas, 350);
  }

  function loadSalas() {
    var seq = ++_salasReqSeq;
    state.salasLoading = true;
    renderSalasPane();
    var qs = buildFilmesQueryString();
    window.dashboardApi.getLatest('theaters', '/api/ancine/salas' + (qs ? '?' + qs : ''))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (seq !== _salasReqSeq) return; // resposta de uma requisição antiga (superada)
        state.salasRows = data || [];
        state.salasLoading = false;
        state.salasPage = 0;
        state.salasLoadedQs = qs;
        renderSalasPane();
      })
      .catch(function () {
        if (seq !== _salasReqSeq) return;
        state.salasLoading = false;
        renderSalasPane();
      });
  }

  function renderSalasPane() {
    var pane = $('pane-salaexibicao');
    if (!pane) return;

    var wrap = pane.querySelector('.table-wrap');
    if (!wrap) {
      pane.innerHTML = '';
      wrap = el('div', { class: 'table-wrap' }, [
        el('div', { class: 'thead', id: 'salas-thead' }),
        el('div', { id: 'salas-tbody' }),
        el('div', { class: 'tpager', id: 'salas-tpager' })
      ]);
      pane.appendChild(wrap);
    }

    if (state.salasLoading) {
      $('salas-thead').innerHTML = '';
      $('salas-tpager').innerHTML = '';
      var body0 = $('salas-tbody'); body0.innerHTML = '';
      body0.appendChild(el('div', { class: 'empty-row' }, 'Carregando…'));
      return;
    }

    var dir = state.salasSortDir === 'asc' ? 1 : -1;
    var sorted = state.salasRows.slice().sort(function (a, b) {
      var av = a[state.salasSortKey], bv = b[state.salasSortKey];
      if (av === null || av === undefined) av = typeof bv === 'string' ? '' : -Infinity;
      if (bv === null || bv === undefined) bv = typeof av === 'string' ? '' : -Infinity;
      if (typeof av === 'string') return av.localeCompare(bv) * dir;
      return (av - bv) * dir;
    });

    var total = sorted.length;
    var totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    state.salasPage = Math.min(state.salasPage, totalPages - 1);
    var start = state.salasPage * PAGE_SIZE;
    var page = sorted.slice(start, start + PAGE_SIZE);

    var head = $('salas-thead'); head.innerHTML = '';
    SALAS_COLUMNS.forEach(function (c) {
      var active = state.salasSortKey === c.key;
      var arrow = active ? (state.salasSortDir === 'asc' ? ' ↑' : ' ↓') : '';
      head.appendChild(el('div', {
        class: 'th' + (c.right ? ' right' : '') + (active ? ' active' : ''),
        onclick: function () {
          if (state.salasSortKey === c.key) state.salasSortDir = state.salasSortDir === 'desc' ? 'asc' : 'desc';
          else { state.salasSortKey = c.key; state.salasSortDir = c.right ? 'desc' : 'asc'; }
          state.salasPage = 0;
          renderSalasPane();
        }
      }, c.label + arrow));
    });

    var body = $('salas-tbody'); body.innerHTML = '';
    if (!page.length) {
      body.appendChild(el('div', { class: 'empty-row' }, 'Nenhuma sala encontrada para os filtros atuais.'));
    } else {
      page.forEach(function (r) {
        var active = state.detailSalaRegistro === r.registroSala;
        body.appendChild(el('div', {
          class: 'trow clickable' + (active ? ' trow-active' : ''),
          onclick: function () { selectSalaDetalhe(r.registroSala); }
        }, [
          el('div', { class: 'cell b' }, r.exibidor || '–'),
          el('div', { class: 'cell muted' }, (r.complexo || '–') + (r.registroComplexo ? ' (' + r.registroComplexo + ')' : '')),
          el('div', { class: 'cell muted' }, (r.sala || '–') + ' (' + r.registroSala + ')'),
          el('div', { class: 'cell mono right' }, fmtInt(r.qtdTitulos)),
          el('div', { class: 'cell mono right' }, fmtInt(r.publicoTotal)),
          el('div', { class: 'cell mono right' }, fmtInt(r.sessoes)),
          el('div', { class: 'cell mono right' }, r.publicoMedioSessao != null ? r.publicoMedioSessao.toFixed(1) : '–')
        ]));
      });
    }

    var pager = $('salas-tpager'); pager.innerHTML = '';
    var from = total ? start + 1 : 0;
    var to = Math.min(start + PAGE_SIZE, total);
    var nav = el('div', { class: 'tpager-nav' }, [
      el('button', {
        class: 'pager-btn' + (state.salasPage === 0 ? ' disabled' : ''),
        onclick: function () { if (state.salasPage > 0) { state.salasPage--; renderSalasPane(); } }
      }, '<'),
      el('span', { class: 'pager-info' }, from + '–' + to + ' / ' + total + ' salas'),
      el('button', {
        class: 'pager-btn' + (state.salasPage >= totalPages - 1 ? ' disabled' : ''),
        onclick: function () { if (state.salasPage < totalPages - 1) { state.salasPage++; renderSalasPane(); } }
      }, '>')
    ]);
    pager.appendChild(nav);
    pager.appendChild(exportButton('salas.csv', SALAS_COLUMNS.map(function (c) { return c.label; }), function () {
      return sorted.map(function (r) { return SALAS_COLUMNS.map(function (c) { return r[c.key]; }); });
    }));
  }

  /* ---------------- Detalhes do Filme (Filme/Diretor/Produtor) ---------------- */
  var _detailReqSeq = 0;
  var _detailRelatedReqSeq = 0;

  function buildRelatedFilmsQueryString(pessoaTab, nome) {
    // Reaproveita buildFilmesQueryString trocando temporariamente
    // nomeDiretor/nomeProdutor/nomeRequerente pelo nome exato clicado
    // (mantendo os demais filtros da sidebar intactos) — não há await entre a
    // troca e a leitura, então é seguro (JS single-thread).
    var savedDiretor = state.nomeDiretor, savedProdutor = state.nomeProdutor, savedRequerente = state.nomeRequerente;
    state.nomeDiretor = pessoaTab === 'diretores' ? nome : '';
    state.nomeProdutor = pessoaTab === 'produtores' ? nome : '';
    state.nomeRequerente = pessoaTab === 'requerente' ? nome : '';
    var qs = buildFilmesQueryString();
    state.nomeDiretor = savedDiretor;
    state.nomeProdutor = savedProdutor;
    state.nomeRequerente = savedRequerente;
    return qs;
  }

  function selectPessoaRelacionada(tab, nome) {
    state.detailPessoa = { tab: tab, nome: nome };
    state.detailRelatedFilms = [];
    state.detailRelatedLoading = true;
    state.detailRelatedPage = 0;
    state.detailCodigo = null;
    state.detailFilme = null;
    state.detailSalaRegistro = null;
    state.detailSala = null;
    state.detailAsideOpen = true;
    renderDetailAside();
    renderFilmesPane(); // no-op se não estiver na aba Filmes; atualiza pane atual (highlight)
    if (state.salasRows.length) renderSalasPane();
    PESSOA_TABS.forEach(function (cfg) { if (state.pessoaTabs[cfg.tab].rows.length) renderPessoaPane(cfg); });

    var seq = ++_detailRelatedReqSeq;
    var qs = buildRelatedFilmsQueryString(tab, nome);
    window.dashboardApi.getLatest('related-films', '/api/ancine/filmes' + (qs ? '?' + qs : ''))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (seq !== _detailRelatedReqSeq) return; // resposta de uma requisição antiga (superada)
        state.detailRelatedFilms = data || [];
        state.detailRelatedLoading = false;
        renderDetailAside();
      })
      .catch(function () {
        if (seq !== _detailRelatedReqSeq) return;
        state.detailRelatedLoading = false;
        renderDetailAside();
      });
  }

  function selectFilmeDetalhe(codigo, keepPessoa) {
    if (!keepPessoa) { state.detailPessoa = null; state.detailRelatedFilms = []; }
    state.detailCodigo = codigo;
    state.detailFilme = null;
    state.detailFilmeLoading = true;
    state.detailCrewTab = 'directors';
    state.detailSalaRegistro = null;
    state.detailSala = null;
    state.detailAsideOpen = true;
    renderDetailAside();
    renderFilmesPane();
    if (state.salasRows.length) renderSalasPane();
    PESSOA_TABS.forEach(function (cfg) { if (state.pessoaTabs[cfg.tab].rows.length) renderPessoaPane(cfg); });

    var seq = ++_detailReqSeq;
    window.dashboardApi.getLatest('film-detail', '/api/ancine/filme-detalhe/' + encodeURIComponent(codigo))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (seq !== _detailReqSeq) return; // resposta de uma requisição antiga (superada)
        state.detailFilme = data;
        state.detailFilmeLoading = false;
        renderDetailAside();
      })
      .catch(function () {
        if (seq !== _detailReqSeq) return;
        state.detailFilme = { ancine: null, imdb: null };
        state.detailFilmeLoading = false;
        renderDetailAside();
      });
  }

  var _detailSalaReqSeq = 0;

  function selectSalaDetalhe(registroSala) {
    state.detailPessoa = null;
    state.detailRelatedFilms = [];
    state.detailCodigo = null;
    state.detailFilme = null;
    state.detailSalaRegistro = registroSala;
    state.detailSala = null;
    state.detailSalaLoading = true;
    state.detailAsideOpen = true;
    renderDetailAside();
    renderSalasPane();
    renderFilmesPane(); // no-op se não estiver na aba Filme; limpa highlight de seleção anterior
    PESSOA_TABS.forEach(function (cfg) { if (state.pessoaTabs[cfg.tab].rows.length) renderPessoaPane(cfg); });

    var seq = ++_detailSalaReqSeq;
    window.dashboardApi.getLatest('theater-detail', '/api/ancine/sala-detalhe/' + encodeURIComponent(registroSala))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (seq !== _detailSalaReqSeq) return; // resposta de uma requisição antiga (superada)
        state.detailSala = data;
        state.detailSalaLoading = false;
        renderDetailAside();
      })
      .catch(function () {
        if (seq !== _detailSalaReqSeq) return;
        state.detailSala = { found: false };
        state.detailSalaLoading = false;
        renderDetailAside();
      });
  }

  function renderDetailAside() {
    // Sincroniza a classe que controla visibilidade com o estado — sem isso,
    // selecionar um filme/pessoa/sala marca detailAsideOpen=true mas não
    // reabre o painel se ele estivesse fechado (relevante no mobile, onde
    // começa fechado por padrão; no desktop já começava aberto, por isso
    // esse gap nunca apareceu antes).
    var detailAsideEl = $('detail-aside');
    if (detailAsideEl) detailAsideEl.classList.toggle('collapsed', !state.detailAsideOpen);
    if (state.tab === 'chat') { renderChatAside(); return; }
    var root = $('detail-aside-scroll');
    if (!root) return;
    root.innerHTML = '';

    if (state.detailSalaRegistro) {
      root.appendChild(renderSalaDetalheBlock());
      return;
    }
    if (state.detailPessoa) root.appendChild(renderRelatedListBlock());
    if (state.detailCodigo) root.appendChild(renderFilmeDetalheBlock());
    if (!state.detailPessoa && !state.detailCodigo) {
      root.appendChild(el('div', { class: 'detail-empty' },
        'Selecione um filme na aba Filme, um diretor/produtor/requerente, ou uma sala na aba Exibidor, para ver aqui os detalhes relacionados.'));
    }
  }

  /* ---------------- Chat com IA ---------------- */
  function renderChatAsideBlock() {
    var wrap = el('div', { class: 'chat-aside' });
    var msgs = el('div', { class: 'chat-messages', id: 'chat-messages' });

    if (!state.chat.messages.length) {
      msgs.appendChild(el('div', { class: 'chat-empty' },
        'Faça uma pergunta em português sobre bilheteria, filmes, diretores, produtores ou salas de exibição — a IA converte para SQL, consulta o banco e responde aqui.'));
    } else {
      state.chat.messages.forEach(function (m, i) {
        if (m.role === 'user') {
          msgs.appendChild(el('div', { class: 'chat-msg chat-msg-user' }, m.text));
          return;
        }
        if (m.loading) {
          msgs.appendChild(el('div', { class: 'chat-msg chat-msg-assistant' }, [
            el('div', { class: 'chat-msg-loading' }, [
              el('span', { class: 'chat-dot' }), el('span', { class: 'chat-dot' }), el('span', { class: 'chat-dot' }),
              el('span', {}, ' consultando…')
            ])
          ]));
          return;
        }
        var isError = !!m.error && !m.sql;
        var bubble = el('div', {
          class: 'chat-msg chat-msg-assistant' + (isError ? ' is-error' : ''),
          onclick: function () { state.chat.selected = i; renderChatResultPane(); renderChatAside(); }
        });
        bubble.appendChild(isError
          ? el('div', {}, 'Erro: ' + m.error)
          : el('div', { html: mdToHtml(m.answer || 'Consulta executada.') }));
        if (!isError) bubble.appendChild(el('div', { class: 'chat-msg-meta' }, (m.rowCount || 0) + ' linha(s) · ' + chatModelLabel(m.model)));
        if (i !== state.chat.selected) bubble.appendChild(el('div', { class: 'chat-select-hint' }, 'ver resultado →'));
        msgs.appendChild(bubble);
      });
    }

    var textarea = el('textarea', {
      class: 'chat-textarea', id: 'chat-textarea', placeholder: 'Ex.: Qual foi o público total em 2024?',
      onkeydown: function (ev) {
        if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); sendChatQuestion(); }
      }
    });
    textarea.value = state.chat.input;
    textarea.addEventListener('input', function () { state.chat.input = textarea.value; });

    var sendBtn = el('button', {
      class: 'chat-send-btn', id: 'chat-send-btn',
      text: state.chat.loading ? 'Enviando…' : 'Enviar',
      onclick: sendChatQuestion
    });
    if (state.chat.loading) sendBtn.disabled = true;

    var modelSelect = el('select', { class: 'chat-model-select', id: 'chat-model-select' });
    if (!state.chat.modelOptions.length) {
      modelSelect.disabled = true;
      modelSelect.appendChild(el('option', {}, state.chat.modelsLoading ? 'Carregando modelos…' : 'Modelo indisponível'));
    } else {
      // Agrupado por provedor (<optgroup>) — com Anthropic/OpenAI/Google/
      // DeepSeek/Alibaba no seletor, uma lista lisa ficaria longa demais.
      var groups = {}, groupOrder = [];
      state.chat.modelOptions.forEach(function (m) {
        var prov = m.provider || 'Outro';
        if (!groups[prov]) { groups[prov] = []; groupOrder.push(prov); }
        groups[prov].push(m);
      });
      groupOrder.forEach(function (prov) {
        var grp = document.createElement('optgroup');
        grp.label = prov;
        groups[prov].forEach(function (m) {
          var opt = el('option', { value: m.id }, m.label);
          if (m.id === state.chat.modelId) opt.selected = true;
          grp.appendChild(opt);
        });
        modelSelect.appendChild(grp);
      });
    }
    modelSelect.addEventListener('change', function () {
      state.chat.modelId = modelSelect.value;
      localStorage.setItem('bilheteria-chat-model', state.chat.modelId);
    });

    wrap.appendChild(msgs);
    wrap.appendChild(el('div', { class: 'chat-model-row' }, [
      el('label', { class: 'chat-model-label' }, 'Modelo de IA'),
      modelSelect
    ]));
    wrap.appendChild(el('div', { class: 'chat-input-row' }, [textarea, sendBtn]));

    setTimeout(function () { msgs.scrollTop = msgs.scrollHeight; }, 0);
    return wrap;
  }

  function loadChatModels() {
    if (state.chat.modelOptions.length || state.chat.modelsLoading) return;
    state.chat.modelsLoading = true;
    window.dashboardApi.getJson('/api/chat/models')
      .then(function (data) {
        state.chat.modelOptions = data || [];
        state.chat.modelsLoading = false;
        var saved = localStorage.getItem('bilheteria-chat-model');
        var isValid = state.chat.modelOptions.some(function (m) { return m.id === saved; });
        if (isValid) {
          state.chat.modelId = saved;
        } else {
          var def = state.chat.modelOptions.filter(function (m) { return m.default; })[0];
          state.chat.modelId = def ? def.id : (state.chat.modelOptions[0] && state.chat.modelOptions[0].id) || null;
        }
        renderChatAside();
      })
      .catch(function () { state.chat.modelsLoading = false; renderChatAside(); });
  }

  function sendChatQuestion() {
    var question = (state.chat.input || '').trim();
    if (!question || state.chat.loading) return;
    state.chat.input = '';
    state.chat.loading = true;
    state.chat.messages.push({ role: 'user', text: question });
    var idx = state.chat.messages.length;
    state.chat.messages.push({ role: 'assistant', loading: true });
    announce('Consultando a inteligência artificial.');
    renderChatAside();

    window.dashboardApi.postJson('/api/chat/query', {
      question: question,
      model: state.chat.modelId
    })
      .then(function (data) {
        state.chat.messages[idx] = {
          role: 'assistant', question: question,
          answer: data.answer, sql: data.sql, columns: data.columns || [],
          rows: data.rows || [], rowCount: data.rowCount || 0, error: data.error, model: data.model,
          page: 0
        };
        state.chat.selected = idx;
        announce(data.error ? 'A consulta falhou.' : 'Resposta da inteligência artificial recebida.');
      })
      .catch(function (err) {
        state.chat.messages[idx] = { role: 'assistant', question: question, error: String(err) };
        announce('Não foi possível concluir a consulta.');
        state.chat.selected = idx;
      })
      .then(function () {
        state.chat.loading = false;
        renderChatAside();
        renderChatResultPane();
      });
  }

  function renderChatAside() {
    var root = $('detail-aside-scroll');
    if (!root || state.tab !== 'chat') return;
    root.innerHTML = '';
    root.appendChild(renderChatAsideBlock());
  }

  function renderChatResultPane() {
    var container = $('pane-chat');
    if (!container) return;
    container.innerHTML = '';
    var wrap = el('div', { class: 'chat-result-pane' });

    var msg = state.chat.selected >= 0 ? state.chat.messages[state.chat.selected] : null;
    if (!msg || msg.loading) {
      wrap.appendChild(el('div', { class: 'chat-empty' }, 'Os resultados da sua pergunta vão aparecer aqui.'));
      container.appendChild(wrap);
      return;
    }

    if (msg.error && !msg.sql) {
      wrap.appendChild(el('div', { class: 'chat-answer-box' }, [
        el('div', { class: 'chat-answer-question' }, msg.question || ''),
        el('div', { class: 'chat-error-box' }, msg.error)
      ]));
      container.appendChild(wrap);
      return;
    }

    wrap.appendChild(el('div', { class: 'chat-answer-box' }, [
      el('div', { class: 'chat-answer-head' }, [
        el('div', { class: 'chat-answer-question' }, msg.question || ''),
        msg.model ? el('div', { class: 'chat-answer-model' }, chatModelLabel(msg.model)) : null
      ]),
      el('div', { html: mdToHtml(msg.answer || '') }),
      el('div', { class: 'chat-answer-actions' }, [
        copyButton('Copiar pergunta e resposta', function () {
          return 'Pergunta: ' + (msg.question || '') + '\n\nResposta: ' + (msg.answer || '');
        })
      ].concat(msg.sql ? [copyButton('Copiar SQL', function () { return msg.sql || ''; })] : []))
    ]));

    if (msg.sql) {
      wrap.appendChild(el('div', {}, [
        el('div', { class: 'chat-sql-label' }, 'SQL executado'),
        el('div', { class: 'chat-sql-box' }, msg.sql)
      ]));
    }

    if (msg.columns && msg.columns.length) {
      var totalRows = msg.rows.length;
      var totalPages = Math.max(1, Math.ceil(totalRows / CHAT_PAGE_SIZE));
      msg.page = Math.min(msg.page || 0, totalPages - 1);
      var start = msg.page * CHAT_PAGE_SIZE;
      var pageRows = msg.rows.slice(start, start + CHAT_PAGE_SIZE);

      var table = el('table', { class: 'chat-result-table' });
      table.appendChild(el('thead', {}, el('tr', {}, msg.columns.map(function (c) { return el('th', {}, c); }))));
      table.appendChild(el('tbody', {}, pageRows.map(function (row) {
        return el('tr', {}, row.map(function (v) { return el('td', {}, v === null || v === undefined ? '–' : String(v)); }));
      })));
      wrap.appendChild(el('div', { class: 'chat-result-table-toolbar' }, [
        el('div', { class: 'chat-sql-label' }, msg.rowCount + ' linha(s)'),
        exportButton('resultado_ia.csv', msg.columns, function () { return msg.rows; })
      ]));

      var tableWrapChildren = [table];
      if (totalPages > 1) {
        var from = totalRows ? start + 1 : 0;
        var to = Math.min(start + CHAT_PAGE_SIZE, totalRows);
        tableWrapChildren.push(el('div', { class: 'tpager' }, [
          el('div', { class: 'tpager-nav' }, [
            el('button', {
              class: 'pager-btn' + (msg.page === 0 ? ' disabled' : ''),
              onclick: function () { if (msg.page > 0) { msg.page--; renderChatResultPane(); } }
            }, '<'),
            el('span', { class: 'pager-info' }, from + '–' + to + ' / ' + totalRows + ' linhas'),
            el('button', {
              class: 'pager-btn' + (msg.page >= totalPages - 1 ? ' disabled' : ''),
              onclick: function () { if (msg.page < totalPages - 1) { msg.page++; renderChatResultPane(); } }
            }, '>')
          ])
        ]));
      }
      wrap.appendChild(el('div', { class: 'chat-result-table-wrap' }, tableWrapChildren));
    }

    container.appendChild(wrap);
  }

  function renderSalaDetalheBlock() {
    var wrap = el('div', { class: 'filme-detalhe-block' }, [
      el('div', { class: 'detail-section-title' }, 'DETALHES DA SALA')
    ]);

    if (state.detailSalaLoading) {
      wrap.appendChild(el('div', { class: 'crew-empty' }, 'Carregando…'));
      return wrap;
    }
    var d = state.detailSala;
    if (!d || !d.found) {
      wrap.appendChild(el('div', { class: 'crew-empty' }, 'Nenhum dado encontrado para esta sala.'));
      return wrap;
    }

    if (d.grupoExibidor) {
      wrap.appendChild(el('div', { class: 'detail-body' }, [
        el('div', { class: 'meta-label' }, 'Grupo Exibidor'),
        el('div', { class: 'detail-title' }, d.grupoExibidor)
      ]));
    }

    var ex = d.exibidor || {};
    wrap.appendChild(el('div', { class: 'detail-body' }, [
      el('div', { class: 'meta-label' }, 'Exibidor'),
      el('div', { class: 'detail-title' }, ex.nome || '–'),
      el('div', { class: 'detail-meta' }, [
        el('div', { class: 'detail-col' }, [metaItem('Registro', ex.registro), metaItem('CNPJ', ex.cnpj)].filter(Boolean)),
        el('div', { class: 'detail-col' }, [metaItem('Situação', ex.situacao)].filter(Boolean))
      ])
    ]));

    var co = d.complexo || {};
    var enderecoLine = [co.endereco, co.numero].filter(Boolean).join(', ') + (co.complemento ? ' - ' + co.complemento : '');
    var municipioUf = [co.municipio, co.uf].filter(Boolean).join('/');
    var cidadeLine = [co.bairro, municipioUf].filter(Boolean).join(' - ');
    wrap.appendChild(el('div', { class: 'detail-body' }, [
      el('div', { class: 'meta-label' }, 'Complexo'),
      el('div', { class: 'detail-title' }, co.nome || '–'),
      el('div', { class: 'detail-meta' }, [
        el('div', { class: 'detail-col' }, [
          metaItem('Registro', co.registro), metaItem('Situação', co.situacao),
          metaItem('Endereço', enderecoLine), metaItem('Bairro/Cidade', cidadeLine)
        ].filter(Boolean)),
        el('div', { class: 'detail-col' }, [
          metaItem('CEP', co.cep), metaItem('Itinerante', co.itinerante),
          metaItem('Operação', co.operacaoUsual), metaItem('Site', co.site)
        ].filter(Boolean))
      ])
    ]));

    var sa = d.sala || {};
    wrap.appendChild(el('div', { class: 'detail-body' }, [
      el('div', { class: 'meta-label' }, 'Sala'),
      el('div', { class: 'detail-title' }, sa.nome || '–'),
      el('div', { class: 'detail-meta' }, [
        el('div', { class: 'detail-col' }, [metaItem('Registro', sa.registro), metaItem('CNPJ', sa.cnpj)].filter(Boolean)),
        el('div', { class: 'detail-col' }, [
          metaItem('Situação', sa.situacao), metaItem('Início Funcionamento', sa.inicioFuncionamento)
        ].filter(Boolean))
      ])
    ]));

    var ac = d.assentos || {};
    wrap.appendChild(el('div', { class: 'detail-body' }, [
      el('div', { class: 'meta-label' }, 'Assentos / Acessibilidade'),
      el('div', { class: 'detail-meta' }, [
        el('div', { class: 'detail-col' }, [
          metaItem('Total', ac.total), metaItem('Cadeirantes', ac.cadeirantes), metaItem('Mobilidade Reduzida', ac.mobilidadeReduzida)
        ].filter(Boolean)),
        el('div', { class: 'detail-col' }, [
          metaItem('Obesidade', ac.obesidade), metaItem('Acesso c/ Rampa', ac.acessoAssentosRampa),
          metaItem('Sala c/ Rampa', ac.acessoSalaRampa), metaItem('Banheiros Acessíveis', ac.banheirosAcessiveis)
        ].filter(Boolean))
      ])
    ]));

    return wrap;
  }

  var RELATED_PAGE_SIZE = 10;

  function renderRelatedListBlock() {
    var pessoaTab = state.detailPessoa.tab;
    var cfg = PESSOA_TABS.filter(function (c) { return c.tab === pessoaTab; })[0];
    var label = cfg ? cfg.label : '';
    var wrap = el('div', { class: 'related-list-block' }, [
      el('div', { class: 'related-list-head' }, [
        el('div', { class: 'detail-section-title' }, 'FILMES RELACIONADOS · ' + label.toUpperCase()),
        el('div', { class: 'related-list-name' }, state.detailPessoa.nome)
      ])
    ]);
    if (state.detailRelatedLoading) {
      wrap.appendChild(el('div', { class: 'crew-empty' }, 'Carregando…'));
      return wrap;
    }
    var films = state.detailRelatedFilms; // já vem ordenado por público desc (/api/ancine/filmes) — o mais relevante primeiro
    if (!films.length) {
      wrap.appendChild(el('div', { class: 'crew-empty' }, 'Nenhum filme encontrado para os filtros atuais.'));
      return wrap;
    }

    var totalPages = Math.max(1, Math.ceil(films.length / RELATED_PAGE_SIZE));
    state.detailRelatedPage = Math.min(state.detailRelatedPage, totalPages - 1);
    var start = state.detailRelatedPage * RELATED_PAGE_SIZE;
    var page = films.slice(start, start + RELATED_PAGE_SIZE);

    page.forEach(function (f) {
      var active = state.detailCodigo === f.codigo;
      wrap.appendChild(el('div', {
        class: 'related-film-row' + (active ? ' trow-active' : ''),
        onclick: function () { selectFilmeDetalhe(f.codigo, true); }
      }, [
        el('div', { class: 'related-film-title' }, f.tituloBrasil || f.tituloOriginal || f.codigo),
        el('div', { class: 'related-film-sub' }, (f.ano1aExibicao || '–') + ' · ' + fmtInt(f.publico) + ' espectadores')
      ]));
    });

    if (films.length > RELATED_PAGE_SIZE) {
      var from = start + 1, to = Math.min(start + RELATED_PAGE_SIZE, films.length);
      wrap.appendChild(el('div', { class: 'tpager' }, [
        el('button', {
          class: 'pager-btn' + (state.detailRelatedPage === 0 ? ' disabled' : ''),
          onclick: function () { if (state.detailRelatedPage > 0) { state.detailRelatedPage--; renderDetailAside(); } }
        }, '<'),
        el('span', { class: 'pager-info' }, from + '–' + to + ' / ' + films.length + ' filmes'),
        el('button', {
          class: 'pager-btn' + (state.detailRelatedPage >= totalPages - 1 ? ' disabled' : ''),
          onclick: function () { if (state.detailRelatedPage < totalPages - 1) { state.detailRelatedPage++; renderDetailAside(); } }
        }, '>')
      ]));
    }
    return wrap;
  }

  function metaItem(label, value) {
    if (value === null || value === undefined || value === '') return null;
    return el('div', { class: 'meta-item' }, [
      el('div', { class: 'meta-label' }, label),
      el('div', { class: 'meta-value' }, String(value))
    ]);
  }

  function renderFilmeDetalheBlock() {
    var wrap = el('div', { class: 'filme-detalhe-block' });

    if (state.detailFilmeLoading) {
      wrap.appendChild(el('div', { class: 'detail-section-title' }, 'DADOS DO FILME'));
      wrap.appendChild(el('div', { class: 'crew-empty' }, 'Carregando…'));
      return wrap;
    }
    var d = state.detailFilme;
    if (!d || !d.ancine) {
      wrap.appendChild(el('div', { class: 'detail-section-title' }, 'DADOS DO FILME'));
      wrap.appendChild(el('div', { class: 'crew-empty' }, 'Nenhum dado encontrado para este título.'));
      return wrap;
    }

    // Bloco Ancine (CPB/ROE) — sempre presente, todo título de bilheteria tem um dos
    // dois — numa coluna só, com o pôster do filme (quando há) ao lado.
    var a = d.ancine;
    var m = d.imdb;
    var ancineCol = el('div', { class: 'detail-col' }, [
      metaItem(a.tipoRegistro, a.codigo),
      metaItem('Tipo de Obra', a.tipoObra),
      metaItem('Duração', a.duracao),
      metaItem('Ano de Produção', a.anoProducao),
      metaItem('Requerente', a.requerente)
    ].filter(Boolean));
    var ancineBody = el('div', { class: 'detail-body' }, [
      el('div', { class: 'detail-title' }, a.titulo || '–'),
      ancineCol
    ]);
    var posterCol = el('div', { class: 'detail-poster-col' });
    if (m && m.poster) {
      posterCol.appendChild(el('img', {
        class: 'detail-poster', src: m.poster, alt: m.title,
        onerror: function (e) { e.target.remove(); }
      }));
    }
    wrap.appendChild(el('div', { class: 'detail-section-title' }, 'DADOS DA OBRA · ANCINE'));
    wrap.appendChild(el('div', { class: 'detail-top' }, (m && m.poster) ? [ancineBody, posterCol] : [ancineBody]));

    if (!m) return wrap;

    // Bloco IMDb — só quando há correspondência (sem selos de avaliação, sem imagem —
    // o pôster já foi mostrado ao lado dos dados Ancine acima).
    var col1 = el('div', { class: 'detail-col' }, [
      metaItem('Ano', m.year), metaItem('Lançamento', m.released), metaItem('Duração', m.runtime),
      metaItem('País', m.country), metaItem('Idioma', m.language)
    ].filter(Boolean));
    var col2 = el('div', { class: 'detail-col' }, [
      metaItem('Gênero', m.genre), metaItem('Direção', m.director), metaItem('Roteiro', m.writer),
      metaItem('Elenco', m.cast), metaItem('Prêmios', m.awards)
    ].filter(Boolean));

    var body = el('div', { class: 'detail-body' }, [
      el('div', { class: 'detail-section-title' }, 'DETALHES DO FILME · IMDB'),
      el('div', { class: 'detail-title' }, m.title),
      el('div', { class: 'detail-meta' }, [col1, col2])
    ]);
    if (m.plot) {
      body.appendChild(el('div', { class: 'detail-plot' }, [
        el('div', { class: 'meta-label' }, 'Sinopse'),
        el('div', {}, m.plot)
      ]));
    }
    wrap.appendChild(body);

    var crew = m.crew || { directors: [], writers: [], cast: [] };
    var crewTabs = [
      { key: 'directors', label: 'Diretores', list: crew.directors },
      { key: 'writers',   label: 'Roteiristas', list: crew.writers },
      { key: 'cast',      label: 'Elenco',     list: crew.cast }
    ];
    if (crewTabs.some(function (t) { return t.list && t.list.length; })) {
      var crewWrap = el('div', { class: 'crew-detail-block' }, [
        el('div', { class: 'detail-section-title' }, 'ELENCO E EQUIPE')
      ]);
      var tabBar = el('div', { class: 'crew-tabs' });
      crewTabs.forEach(function (t) {
        tabBar.appendChild(el('button', {
          class: 'crew-tab-btn' + (state.detailCrewTab === t.key ? ' active' : ''),
          onclick: function () { state.detailCrewTab = t.key; renderDetailAside(); }
        }, t.label + ' (' + (t.list ? t.list.length : 0) + ')'));
      });
      crewWrap.appendChild(tabBar);

      var activeTab = crewTabs.filter(function (t) { return t.key === state.detailCrewTab; })[0] || crewTabs[0];
      var panel = el('div', { class: 'crew-panel' });
      if (!activeTab.list || !activeTab.list.length) {
        panel.appendChild(el('div', { class: 'crew-empty' }, 'Sem dados de ' + activeTab.label.toLowerCase() + ' no IMDb.'));
      } else {
        activeTab.list.forEach(function (p) { panel.appendChild(buildCrewCard(p)); });
      }
      crewWrap.appendChild(panel);
      wrap.appendChild(crewWrap);
    }

    return wrap;
  }

  function buildCrewCard(p) {
    var card = el('div', { class: 'crew-card' });
    if (p.photo) {
      card.appendChild(el('img', {
        class: 'crew-photo', src: p.photo, alt: p.name,
        onerror: function (e) { e.target.className = 'crew-photo-placeholder'; e.target.removeAttribute('src'); }
      }));
    } else {
      card.appendChild(el('div', { class: 'crew-photo-placeholder' }));
    }
    var info = el('div', { class: 'crew-info' }, [el('div', { class: 'crew-name' }, p.name)]);
    var FIELDS = [
      ['Categoria', p.category], ['Função', p.job], ['Personagens', p.characters],
      ['Gênero', p.gender], ['Nacionalidade', p.nationality], ['Etnia', p.ethnicity],
      ['Religião', p.religion], ['Raça', p.race], ['Nascimento', p.born]
    ];
    FIELDS.forEach(function (f) {
      if (!f[1]) return;
      info.appendChild(el('div', { class: 'crew-field' }, [f[0] + ': ', el('b', {}, f[1])]));
    });
    if (p.biography) {
      info.appendChild(el('div', { class: 'crew-bio' }, p.biography.length > 260 ? p.biography.slice(0, 260) + '…' : p.biography));
    }
    card.appendChild(info);
    return card;
  }

  function filterFilms() {
    // Os filtros da sidebar (Período/Obra/Sala de Exibição/Diretor/Produtor/
    // Requerente) operam sobre os dados de bilheteria/Ancine (data/ancine/),
    // que ainda não são servidos pela API — por ora não há nada para filtrar
    // no dataset atual (MovieLens/IMDb, data/imdb/). Será ligado quando os
    // endpoints de bilheteria existirem.
    return FILMS;
  }

  /* ---------------- Sidebar build ---------------- */
  var filterUpdaters = [];
  var groupRefs = {};

  function buildSidebar() {
    var root = $('sidebar');
    root.innerHTML = '';
    root.appendChild(el('div', { class: 'filters-title', html: '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3"><path d="M1.5 3h13l-5 6v5l-3-1.6V9z"/></svg>FILTROS' }));

    // PERÍODO group
    var periodoBody = el('div', { class: 'group-body' });
    root.appendChild(groupHeader('periodo', 'PERÍODO'));
    root.appendChild(periodoBody);
    addFilter(periodoBody, 'anos', 'ANO', function () { return PERIODO_OPTIONS.anos; }, true);
    addRange(periodoBody, 'semanaInicio', 'semanaFim', 'SEMANA CINEMATOGRÁFICA', 1, 53);

    // OBRA group
    var obraBody = el('div', { class: 'group-body collapsed' });
    root.appendChild(groupHeader('obra', 'FILME'));
    root.appendChild(obraBody);
    addSearch(obraBody, 'cpbRoe', 'CPB/ROE', 'Buscar por CPB ou ROE...');
    addSearchAutocomplete(obraBody, 'tituloBrasileiro', 'TÍTULO BRASILEIRO', 'Buscar por título brasileiro...', '/api/ancine/titulo-brasil-sugestoes');
    addSearch(obraBody, 'tituloOriginal', 'TÍTULO ORIGINAL', 'Buscar por título original...');
    addFilter(obraBody, 'paisOrigem', 'PAÍS DE ORIGEM', function () { return OBRA_OPTIONS.paisOrigem; });

    // DIRETOR group
    var diretorBody = el('div', { class: 'group-body collapsed' });
    root.appendChild(groupHeader('diretor', 'DIRETOR'));
    root.appendChild(diretorBody);
    addSearch(diretorBody, 'nomeDiretor', 'NOME DIRETOR', 'Buscar por nome do diretor...');

    // PRODUTOR group
    var produtorBody = el('div', { class: 'group-body collapsed' });
    root.appendChild(groupHeader('produtor', 'PRODUTOR'));
    root.appendChild(produtorBody);
    addSearch(produtorBody, 'nomeProdutor', 'NOME PRODUTOR', 'Buscar por nome do produtor...');

    // REQUERENTE group
    var requerenteBody = el('div', { class: 'group-body collapsed' });
    root.appendChild(groupHeader('requerente', 'REQUERENTE'));
    root.appendChild(requerenteBody);
    addSearch(requerenteBody, 'cnpjRequerente', 'CNPJ REQUERENTE', 'Buscar por CNPJ...');
    addSearch(requerenteBody, 'nomeRequerente', 'NOME REQUERENTE', 'Buscar por nome do requerente...');
    addFilter(requerenteBody, 'municipioRequerente', 'MUNICÍPIO', function () { return []; });
    addFilter(requerenteBody, 'ufRequerente', 'UF REQUERENTE', function () { return []; });

    // EXIBIDOR group
    var salaBody = el('div', { class: 'group-body collapsed' });
    root.appendChild(groupHeader('salaexibicao', 'EXIBIDOR'));
    root.appendChild(salaBody);
    addFilter(salaBody, 'grupoExibidor', 'GRUPO EXIBIDOR', salaGrupoOptions);
    addSearch(salaBody, 'registroSala', 'REGISTRO COMPLEXO OU SALA', 'Buscar por registro...');
    addFilter(salaBody, 'ufSala', 'UF', salaUfOptions);
    addFilter(salaBody, 'municipioSala', 'MUNICÍPIO', salaMunicipioOptions);

    groupRefs.periodo.body = periodoBody;
    groupRefs.obra.body = obraBody;
    groupRefs.diretor.body = diretorBody;
    groupRefs.produtor.body = produtorBody;
    groupRefs.requerente.body = requerenteBody;
    groupRefs.salaexibicao.body = salaBody;
  }

  function groupHeader(key, label) {
    var badge = el('span', { class: 'group-badge', style: 'display:none' }, '0');
    var chev = el('span', { class: 'chev' }, state.open[key] ? '▾' : '▸');
    var head = el('div', { class: 'group-header', onclick: function () {
      state.open[key] = !state.open[key];
      groupRefs[key].body.classList.toggle('collapsed', !state.open[key]);
      chev.textContent = state.open[key] ? '▾' : '▸';
    } }, [
      el('div', { class: 'group-left' }, [el('span', { class: 'group-name' }, label), badge]),
      chev
    ]);
    groupRefs[key] = { badge: badge, chev: chev };
    return head;
  }

  function addFilter(parent, key, label, allFn, numeric) {
    var field = el('div', { class: 'field' });
    field.appendChild(el('div', { class: 'field-label' }, label));
    var select = el('select');
    var sw = el('div', { class: 'select-wrap' }, [select, el('span', { class: 'chev-down', html: '&#9662;' })]);
    field.appendChild(sw);
    var chips = el('div', { class: 'chips' });
    field.appendChild(chips);
    parent.appendChild(field);

    select.addEventListener('change', function () {
      var v = select.value;
      if (v === '') return;
      var val = numeric ? parseInt(v, 10) : v;
      if (state[key].indexOf(val) < 0) { state[key] = state[key].concat([val]); render(); }
      select.value = '';
    });

    function update() {
      var sel = state[key];
      var all = allFn();
      // options
      select.innerHTML = '';
      select.appendChild(new Option(sel.length ? 'Add…' : 'Selecione...', ''));
      all.forEach(function (x) { if (sel.indexOf(numeric ? x : x) < 0) select.appendChild(new Option(String(x), String(x))); });
      select.value = '';
      // chips
      chips.innerHTML = '';
      chips.style.display = sel.length ? 'flex' : 'none';
      sel.slice().sort(function (a, b) { return numeric ? a - b : String(a).localeCompare(String(b)); }).forEach(function (x) {
        chips.appendChild(el('div', { class: 'chip', onclick: function () {
          state[key] = state[key].filter(function (z) { return z !== x; }); render();
        } }, [String(x), el('span', { class: 'chip-x', html: '&times;' })]));
      });
    }
    filterUpdaters.push(update);
  }

  function addRange(parent, keyFrom, keyTo, label, min, max) {
    var field = el('div', { class: 'field' });
    field.appendChild(el('div', { class: 'field-label' }, label));
    var inpFrom = el('input', {
      type: 'number', class: 'search range-input', placeholder: 'De', min: String(min), max: String(max),
      oninput: function (e) { state[keyFrom] = e.target.value; render(); }
    });
    var inpTo = el('input', {
      type: 'number', class: 'search range-input', placeholder: 'Até', min: String(min), max: String(max),
      oninput: function (e) { state[keyTo] = e.target.value; render(); }
    });
    field.appendChild(el('div', { class: 'range-wrap' }, [inpFrom, el('span', { class: 'range-sep' }, '–'), inpTo]));
    parent.appendChild(field);
    filterUpdaters.push(function () { inpFrom.value = state[keyFrom]; inpTo.value = state[keyTo]; });
  }

  function addSearch(parent, key, label, placeholder) {
    var field = el('div', { class: 'field' });
    field.appendChild(el('div', { class: 'field-label' }, label));
    var inp = el('input', {
      id: 'search-' + key, class: 'search', placeholder: placeholder || '',
      oninput: function (e) { state[key] = e.target.value; render(); }
    });
    field.appendChild(inp);
    parent.appendChild(field);
    filterUpdaters.push(function () { inp.value = state[key]; });
  }

  var _suggestDebounce = {};
  var _suggestReqSeq = {};

  function addSearchAutocomplete(parent, key, label, placeholder, endpoint) {
    var field = el('div', { class: 'field autocomplete-field' });
    field.appendChild(el('div', { class: 'field-label' }, label));
    var dropdown = el('div', { class: 'autocomplete-dropdown' });
    var inp = el('input', {
      id: 'search-' + key, class: 'search', placeholder: placeholder || '', autocomplete: 'off',
      oninput: function (e) {
        state[key] = e.target.value;
        scheduleSuggest(key, endpoint, e.target.value, dropdown);
        render();
      },
      onfocus: function (e) { scheduleSuggest(key, endpoint, e.target.value, dropdown); },
      onblur: function () { setTimeout(function () { dropdown.style.display = 'none'; }, 150); }
    });
    field.appendChild(inp);
    field.appendChild(dropdown);
    parent.appendChild(field);
    filterUpdaters.push(function () { inp.value = state[key]; });

    function scheduleSuggest(k, url, q, dd) {
      if (_suggestDebounce[k]) clearTimeout(_suggestDebounce[k]);
      if (!q || q.trim().length < 2) { dd.style.display = 'none'; dd.innerHTML = ''; return; }
      _suggestDebounce[k] = setTimeout(function () { loadSuggest(k, url, q, dd); }, 250);
    }

    function loadSuggest(k, url, q, dd) {
      var seq = (_suggestReqSeq[k] = (_suggestReqSeq[k] || 0) + 1);
      fetch(url + '?q=' + encodeURIComponent(q))
        .then(function (r) { return r.json(); })
        .then(function (list) {
          if (seq !== _suggestReqSeq[k]) return; // resposta de uma requisição antiga (superada)
          dd.innerHTML = '';
          if (!list || !list.length) { dd.style.display = 'none'; return; }
          list.forEach(function (item) {
            dd.appendChild(el('div', {
              class: 'autocomplete-item',
              onmousedown: function (e) {
                e.preventDefault(); // evita que o blur do input feche o dropdown antes do clique
                state[key] = item;
                dd.style.display = 'none';
                render();
              }
            }, item));
          });
          dd.style.display = 'block';
        })
        .catch(function () {});
    }
  }

  /* ---------------- Render ---------------- */
  var _bubbles = [], _dirBubbles = [], _wriBubbles = [], _world = null, _worldLoading = false, _ro = null, _ro2 = null, _ro3 = null, _ro4 = null, _ro5 = null, _ro6 = null, _lastSig = null;

  /* ---------------- Período exibido no header (todas as abas) ---------------- */
  var _periodoExibidoDebounce = null;
  var _periodoExibidoReqSeq = 0;

  function schedulePeriodoExibido() {
    if (_periodoExibidoDebounce) clearTimeout(_periodoExibidoDebounce);
    _periodoExibidoDebounce = setTimeout(loadPeriodoExibido, 350);
  }

  function loadPeriodoExibido() {
    var seq = ++_periodoExibidoReqSeq;
    var qs = buildFilmesQueryString();
    window.dashboardApi.getLatest('display-period', '/api/ancine/periodo-exibido' + (qs ? '?' + qs : ''))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (seq !== _periodoExibidoReqSeq) return; // resposta de uma requisição antiga (superada)
        var el = $('periodo-subtitle');
        if (data && data.dataMin && data.dataMax) {
          el.textContent = 'De ' + data.dataMin + ' até ' + data.dataMax;
        } else {
          el.textContent = 'Nenhum resultado para os filtros selecionados';
        }
      })
      .catch(function () {});
  }

  function render() {
    var fs = filterFilms();
    syncStateToUrl();

    // período exibido (data mín/máx de exibição), de acordo com os filtros —
    // mostrado no header, em todas as abas
    if (PERIODO_OPTIONS.dataMin && PERIODO_OPTIONS.dataMax && !$('periodo-subtitle').textContent) {
      $('periodo-subtitle').textContent = 'De ' + PERIODO_OPTIONS.dataMin + ' até ' + PERIODO_OPTIONS.dataMax;
    }
    schedulePeriodoExibido();

    // group badges
    setBadge('periodo',     cnt(['anos']) + (state.semanaInicio ? 1 : 0) + (state.semanaFim ? 1 : 0));
    setBadge('obra',        (state.cpbRoe ? 1 : 0) + (state.tituloBrasileiro ? 1 : 0) + (state.tituloOriginal ? 1 : 0) + cnt(['paisOrigem']));
    setBadge('salaexibicao', (state.registroSala ? 1 : 0) + cnt(['grupoExibidor','municipioSala','ufSala']));
    setBadge('diretor',     state.nomeDiretor ? 1 : 0);
    setBadge('produtor',    state.nomeProdutor ? 1 : 0);
    setBadge('requerente',  (state.cnpjRequerente ? 1 : 0) + (state.nomeRequerente ? 1 : 0) + cnt(['municipioRequerente','ufRequerente']));

    // filters
    filterUpdaters.forEach(function (u) { u(); });

    // painel "Detalhes do Filme"/"Detalhes da Sala"/"Chat com IA" — só faz
    // sentido nas abas Filme/Diretor/Produtor/Requerente/Exibidor/Chat
    var showDetail = state.tab === 'filmes' || state.tab === 'diretores' || state.tab === 'produtores' ||
      state.tab === 'requerente' || state.tab === 'salaexibicao' || state.tab === 'chat';
    var detailAside = $('detail-aside'), detailToggleBtn = $('detail-toggle');
    if (detailAside) detailAside.classList.toggle('inactive-tab', !showDetail);
    if (detailToggleBtn) detailToggleBtn.classList.toggle('inactive-tab', !showDetail);

    // tab content — só refaz o fetch se os filtros atuais forem diferentes
    // do que já está carregado para aquela aba (loadedQs); troca de aba sem
    // mudar filtro não deve gerar requisição nova.
    var activeQs = buildFilmesQueryString();
    if (state.tab === 'bilheteria' && state.bilheteriaLoadedQs !== activeQs) scheduleLoadBilheteria();
    if (state.tab === 'filmes' && state.filmesLoadedQs !== activeQs) scheduleLoadFilmes();
    if (state.tab === 'salaexibicao' && state.salasLoadedQs !== activeQs) scheduleLoadSalas();
    if (state.tab === 'paises' && state.paisesLoadedQs !== activeQs) scheduleLoadPaises();
    if (state.tab === 'chat') renderChatResultPane();
    PESSOA_TABS.forEach(function (cfg) {
      var st = state.pessoaTabs[cfg.tab];
      if (state.tab === cfg.tab && st.loadedQs !== activeQs) schedulePessoaLoad(cfg);
    });
  }
  function sum(a, k) { return a.reduce(function (s, f) { return s + f[k]; }, 0); }
  function cnt(keys) { return keys.reduce(function (s, k) { return s + state[k].length; }, 0); }
  function setBadge(key, n) {
    var b = groupRefs[key].badge; b.textContent = n; b.style.display = n > 0 ? 'inline-block' : 'none';
  }

  /* ---------------- Distribution strip ---------------- */
  function renderDist(fs) {
    var gc = {}; fs.forEach(function (f) { gc[f.genre] = (gc[f.genre] || 0) + 1; });
    var arr = Object.keys(gc).map(function (g) { return { g: g, n: gc[g] }; }).sort(function (a, b) { return b.n - a.n; });
    var max = Math.max.apply(null, [1].concat(arr.map(function (d) { return d.n; })));
    var row = $('dist-row'); row.innerHTML = '';
    arr.forEach(function (d) {
      row.appendChild(el('div', { class: 'dist-item' }, [
        el('div', { class: 'dist-bar', style: 'height:' + (10 + d.n / max * 42) + 'px;background:' + colorOf(d.g) }),
        el('div', { class: 'dist-cap' }, [el('div', { class: 'dist-genre' }, d.g), el('div', { class: 'dist-count' }, d.n)])
      ]));
    });
  }

  /* ---------------- Diversity ---------------- */
  function renderDiversity(fs) {
    var grid = $('div-grid'); grid.innerHTML = '';
    grid.appendChild(diversityPanel(fs, 'dir', 'DIRECTOR'));
    grid.appendChild(diversityPanel(fs, 'wri', 'WRITER'));
  }

  function renderTopPersonCharts() {
    var grid = $('top-persons-grid');
    if (!grid) return;
    grid.innerHTML = '';
    var TOP_N = 15;
    var purpleColor = cssVar('--map-purple');
    var tealColor   = cssVar('--map-teal');

    var dirTop = _dirBubbles.slice().sort(function (a, b) { return b.count - a.count; }).slice(0, TOP_N);
    grid.appendChild(hbarChart('Top Countries · Directors',
      dirTop.map(function (d) { return { label: d.country, n: d.count, color: purpleColor }; })));

    var wriTop = _wriBubbles.slice().sort(function (a, b) { return b.count - a.count; }).slice(0, TOP_N);
    grid.appendChild(hbarChart('Top Countries · Writers',
      wriTop.map(function (d) { return { label: d.country, n: d.count, color: tealColor }; })));
  }
  function diversityPanel(fs, key, title) {
    var total = fs.length || 1;
    // race
    var rc = {}; RACES.forEach(function (r) { rc[r] = 0; });
    fs.forEach(function (f) { rc[f[key].race] = (rc[f[key].race] || 0) + 1; });
    var rMax = Math.max.apply(null, [1].concat(RACES.map(function (r) { return rc[r]; })));
    var raceCol = el('div', {}, [el('div', { class: 'div-sub' }, 'Race')]);
    RACES.forEach(function (r) {
      raceCol.appendChild(el('div', { class: 'race-row' }, [
        el('div', { class: 'race-label' }, [el('span', { class: 'race-dot', style: 'background:' + RACE_COLORS[r] }), r]),
        el('div', { class: 'race-track' }, el('div', { class: 'race-fill', style: 'width:' + (rc[r] / rMax * 100) + '%;background:' + RACE_COLORS[r] })),
        el('div', { class: 'race-pct' }, Math.round(rc[r] / total * 100) + '%')
      ]));
    });
    // gender
    var g = { Male: 0, Female: 0, Unknown: 0 };
    fs.forEach(function (f) { g[f[key].gender] = (g[f[key].gender] || 0) + 1; });
    var gp = function (n) { return Math.round(n / total * 100); };
    var maleFig = '<svg width="34" height="74" viewBox="0 0 40 80"><circle cx="20" cy="11" r="9" fill="' + MALE_C + '"/><rect x="9" y="23" width="22" height="34" rx="9" fill="' + MALE_C + '"/><rect x="13" y="50" width="6" height="26" rx="3" fill="' + MALE_C + '"/><rect x="21" y="50" width="6" height="26" rx="3" fill="' + MALE_C + '"/></svg>';
    var femFig = '<svg width="34" height="74" viewBox="0 0 40 80"><circle cx="20" cy="11" r="9" fill="' + FEMALE_C + '"/><path d="M20 21 L34 60 H6 Z" fill="' + FEMALE_C + '"/><rect x="15" y="58" width="4" height="18" rx="2" fill="' + FEMALE_C + '"/><rect x="21" y="58" width="4" height="18" rx="2" fill="' + FEMALE_C + '"/></svg>';
    var genderCol = el('div', {}, [
      el('div', { class: 'div-sub' }, 'Gender'),
      el('div', { class: 'gender-figs', html: maleFig + femFig }),
      el('div', { class: 'gender-legend' }, [
        glRow('Male', gp(g.Male), MALE_C),
        glRow('Female', gp(g.Female), FEMALE_C),
        glRow('Unknown', gp(g.Unknown), '#8b97a8')
      ])
    ]);
    // age pyramid
    var bands = [['> 60', 61, 999], ['51 a 60', 51, 60], ['41 a 50', 41, 50], ['31 a 40', 31, 40], ['21 a 30', 21, 30], ['ate 20', 0, 20]];
    var rows = bands.map(function (b) {
      var male = 0, female = 0;
      fs.forEach(function (f) { var p = f[key]; if (p.age != null && p.age >= b[1] && p.age <= b[2]) { if (p.gender === 'Male') male++; else if (p.gender === 'Female') female++; } });
      return { label: b[0], male: male, female: female };
    });
    var aMax = Math.max.apply(null, [1].concat(rows.map(function (r) { return Math.max(r.male, r.female); })));
    var ageCol = el('div', {}, [
      el('div', { class: 'age-head' }, [
        el('span', { class: 'age-key age-bar-key m' }), 'Men',
        el('span', { style: 'color:var(--dim)' }, '|'), 'Women',
        el('span', { class: 'age-key age-bar-key f' })
      ])
    ]);
    rows.forEach(function (r) {
      ageCol.appendChild(el('div', { class: 'age-row' }, [
        el('div', { class: 'age-side' }, el('div', { class: 'age-bar male', style: 'width:' + (r.male / aMax * 100) + '%' })),
        el('div', { class: 'age-label' }, r.label),
        el('div', { class: 'age-side' }, el('div', { class: 'age-bar female', style: 'width:' + (r.female / aMax * 100) + '%' }))
      ]));
    });

    return el('div', { class: 'div-panel' }, [
      el('div', { class: 'div-title' }, title + ' DIVERSITY'),
      el('div', { class: 'div-cols' }, [genderCol, ageCol, raceCol])
    ]);
  }
  function glRow(name, pct, color) {
    return el('div', { class: 'gl-row' }, [
      el('span', { class: 'gl-dot', style: 'background:' + color }),
      el('span', { class: 'gl-name' }, name),
      el('span', { class: 'gl-pct' }, pct + '%')
    ]);
  }

  /* ---------------- Charts ---------------- */
  function hbarChart(title, arr, fmtVal) {
    var max = Math.max.apply(null, [1].concat(arr.map(function (d) { return d.n; })));
    var card = chartCard(title);
    arr.forEach(function (d) {
      card.appendChild(el('div', { class: 'hbar-row' }, [
        el('div', { class: 'hbar-label' }, d.label),
        el('div', { class: 'hbar-track' }, el('div', { class: 'hbar-fill', style: 'width:' + (d.n ? Math.max(6, d.n / max * 100) : 0) + '%;' + (d.color ? 'background:' + d.color : '') })),
        el('div', { class: 'hbar-val' }, fmtVal ? fmtVal(d.n) : d.n)
      ]));
    });
    return card;
  }

  function vbarChart(title, buckets, valueKey, fmtVal) {
    var max = Math.max.apply(null, [1].concat(buckets.map(function (b) { return b[valueKey]; })));
    var card = chartCard(title);
    var bars = el('div', { class: 'rbars' });
    buckets.forEach(function (b) {
      var v = b[valueKey];
      bars.appendChild(el('div', { class: 'vcol' }, [
        el('div', { class: 'vval' }, fmtVal ? fmtVal(v) : v),
        el('div', { class: 'vbar' + (v ? '' : ' empty'), style: 'width:46px;height:' + (v / max * 100) + '%;min-height:' + (v ? 4 : 2) + 'px' }),
        el('div', { class: 'vlabel' }, b.label)
      ]));
    });
    card.appendChild(bars);
    return card;
  }

  function renderCharts(fs) {
    var wrap = $('charts-scroll'); wrap.innerHTML = '';

    // ── Pair 1: Genre Distribution | Films by Decade ─────────────────────────
    var gc = {}; fs.forEach(function (f) { gc[f.genre] = (gc[f.genre] || 0) + 1; });
    var gArr = Object.keys(gc).map(function (g) { return { label: g, n: gc[g], color: colorOf(g) }; }).sort(function (a, b) { return b.n - a.n; });
    wrap.appendChild(hbarChart('Genre Distribution', gArr));

    var dc = {};
    fs.forEach(function (f) { if (f.year != null) { var di = Math.floor((f.year - 1) / 10); dc[di] = (dc[di] || 0) + 1; } });
    var allDI = YEARS.map(function (y) { return Math.floor((y - 1) / 10); });
    var minDI = Math.min.apply(null, allDI), maxDI = Math.max.apply(null, allDI);
    var decades = [];
    for (var di = maxDI; di >= minDI; di--) {
      var dStart = di * 10 + 1, dEnd = di === maxDI ? YEARS[YEARS.length - 1] : dStart + 9;
      decades.push({ label: dStart + '–' + dEnd, n: dc[di] || 0 });
    }
    wrap.appendChild(hbarChart('Films by Decade', decades));

    // ── Pair 2: Continent Distribution | Region Distribution ─────────────────
    var cc = {}, rc = {};
    fs.forEach(function (f) {
      if (f.continent && f.continent !== 'Other') cc[f.continent] = (cc[f.continent] || 0) + 1;
      if (f.region) rc[f.region] = (rc[f.region] || 0) + 1;
    });
    wrap.appendChild(hbarChart('Continent Distribution',
      Object.keys(cc).map(function (k) { return { label: k, n: cc[k] }; }).sort(function (a, b) { return b.n - a.n; })));
    wrap.appendChild(hbarChart('Region Distribution',
      Object.keys(rc).map(function (k) { return { label: k, n: rc[k] }; }).sort(function (a, b) { return b.n - a.n; })));

    // ── Pair 3: Rating Distribution ML | Rating Distribution IMDB ────────────
    var mlBuckets = [
      { label: '<3.5', min: 0,   max: 3.5 }, { label: '3.5–4.0', min: 3.5, max: 4.0 },
      { label: '4.0–4.5', min: 4.0, max: 4.5 }, { label: '4.5+',  min: 4.5, max: 99  }
    ];
    mlBuckets.forEach(function (b) { b.count = fs.filter(function (f) { return f.ratingMl >= b.min && f.ratingMl < b.max; }).length; });
    wrap.appendChild(vbarChart('Rating Distribution — ML', mlBuckets, 'count'));

    var imBuckets = [
      { label: '<7.0', min: 0, max: 7 }, { label: '7.0-7.5', min: 7, max: 7.5 },
      { label: '7.5-8.0', min: 7.5, max: 8 }, { label: '8.0+', min: 8, max: 99 }
    ];
    imBuckets.forEach(function (b) { b.count = fs.filter(function (f) { return f.rating >= b.min && f.rating < b.max; }).length; });
    wrap.appendChild(vbarChart('Rating Distribution — IMDB', imBuckets, 'count'));

    // ── Pair 4: Oscars Winning by Continent | Oscars Winning by Region ────────
    var oc = {}, or_ = {};
    fs.forEach(function (f) {
      if (f.oscars) {
        if (f.continent && f.continent !== 'Other') oc[f.continent] = (oc[f.continent] || 0) + f.oscars;
        if (f.region) or_[f.region] = (or_[f.region] || 0) + f.oscars;
      }
    });
    wrap.appendChild(hbarChart('Oscars Winning by Continent',
      Object.keys(oc).map(function (k) { return { label: k, n: oc[k] }; }).sort(function (a, b) { return b.n - a.n; })));
    wrap.appendChild(hbarChart('Oscars Winning by Region',
      Object.keys(or_).map(function (k) { return { label: k, n: or_[k] }; }).sort(function (a, b) { return b.n - a.n; })));

    // ── Pair 5: Other Awards by Continent | Other Awards by Region ────────────
    var awc = {}, awr = {};
    fs.forEach(function (f) {
      if (f.otherAwards) {
        if (f.continent && f.continent !== 'Other') awc[f.continent] = (awc[f.continent] || 0) + f.otherAwards;
        if (f.region) awr[f.region] = (awr[f.region] || 0) + f.otherAwards;
      }
    });
    wrap.appendChild(hbarChart('Other Awards by Continent',
      Object.keys(awc).map(function (k) { return { label: k, n: awc[k] }; }).sort(function (a, b) { return b.n - a.n; })));
    wrap.appendChild(hbarChart('Other Awards by Region',
      Object.keys(awr).map(function (k) { return { label: k, n: awr[k] }; }).sort(function (a, b) { return b.n - a.n; })));

    // ── Single: MovieLens Votes by Rating (full width) ────────────────────────
    if (RATINGS_DIST.length) {
      var mlMax = Math.max.apply(null, RATINGS_DIST.map(function (d) { return d.votes; }));
      var cml = chartCard('MovieLens Votes by Rating');
      cml.style.gridColumn = '1 / -1';
      var mlb = el('div', { class: 'vbars' });
      RATINGS_DIST.forEach(function (d) {
        mlb.appendChild(el('div', { class: 'vcol' }, [
          el('div', { class: 'vval' }, fmtVotes(d.votes)),
          el('div', { class: 'vbar', style: 'height:' + (d.votes / mlMax * 100) + '%;min-height:4px' }),
          el('div', { class: 'vlabel' }, d.rating.toFixed(1))
        ]));
      });
      cml.appendChild(mlb); wrap.appendChild(cml);
    }
  }
  function chartCard(title) { return el('div', { class: 'chart-card' }, [el('div', { class: 'chart-title' }, title)]); }

  /* ---------------- Table ---------------- */
  var COLUMNS = [
    { key: 'title',       label: 'Title' },
    { key: 'director',    label: 'Director' },
    { key: 'year',        label: 'Year',        right: true },
    { key: 'country',     label: 'Country' },
    { key: 'genre',       label: 'Genre' },
    { key: 'rating',      label: 'IMDb ★',  right: true },
    { key: 'ratingMl',    label: 'ML ★',    right: true },
    { key: 'votesMl',     label: 'ML Votes',    right: true },
    { key: 'box',         label: 'Box',         right: true },
    { key: 'oscars',      label: 'Oscars',      right: true },
    { key: 'otherAwards', label: 'Awards',      right: true }
  ];
  function renderTable(fs) {
    // Sort
    var dir = state.sortDir === 'asc' ? 1 : -1;
    var sorted = fs.slice().sort(function (a, b) {
      var av = a[state.sortKey], bv = b[state.sortKey];
      if (typeof av === 'string') return av.localeCompare(bv) * dir;
      return (av - bv) * dir;
    });

    var total = sorted.length;
    var totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    state.tablePage = Math.min(state.tablePage, totalPages - 1);
    var start = state.tablePage * PAGE_SIZE;
    var page = sorted.slice(start, start + PAGE_SIZE);

    // Header
    var head = $('thead'); head.innerHTML = '';
    COLUMNS.forEach(function (c) {
      var active = state.sortKey === c.key;
      var arrow = active ? (state.sortDir === 'asc' ? ' ↑' : ' ↓') : '';
      head.appendChild(el('div', {
        class: 'th' + (c.right ? ' right' : '') + (active ? ' active' : ''),
        onclick: function () {
          if (state.sortKey === c.key) state.sortDir = state.sortDir === 'desc' ? 'asc' : 'desc';
          else { state.sortKey = c.key; state.sortDir = 'desc'; }
          state.tablePage = 0;
          renderTable(fs);
        }
      }, c.label + arrow));
    });

    // Body — only current page
    var body = $('tbody'); body.innerHTML = '';
    if (!page.length) {
      body.appendChild(el('div', { class: 'empty-row' }, 'No films match the current filters.'));
    } else {
      page.forEach(function (f) {
        body.appendChild(el('div', { class: 'trow' }, [
          el('div', { class: 'cell b', title: 'MovieID: ' + (f.movieid || '–') + ' | IMDb: ' + f.imdbid }, f.title),
          el('div', { class: 'cell muted', title: f.directorid ? 'DirectorID: ' + f.directorid : '' }, f.directorsAll || f.director),
          el('div', { class: 'cell mono right' }, f.year),
          el('div', { class: 'cell muted' }, f.countriesAll || f.country),
          el('div', { class: 'cell genre' }, [el('span', { class: 'gdot', style: 'background:' + colorOf(f.genre) }), f.genresAll || f.genre]),
          el('div', { class: 'cell bold right' }, '★ ' + f.rating.toFixed(1)),
          el('div', { class: 'cell mono right' }, f.ratingMl ? '★ ' + f.ratingMl.toFixed(1) : '–'),
          el('div', { class: 'cell mono right' }, f.votesMl ? fmtVotes(f.votesMl) : '–'),
          el('div', { class: 'cell mono right' }, fmtMoney(f.box)),
          el('div', { class: 'cell mono right' }, f.oscars || '–'),
          el('div', { class: 'cell mono right' }, f.otherAwards || '–')
        ]));
      });
    }

    // Pager
    var pager = $('tpager'); pager.innerHTML = '';
    var from = total ? start + 1 : 0;
    var to = Math.min(start + PAGE_SIZE, total);
    pager.appendChild(el('button', {
      class: 'pager-btn' + (state.tablePage === 0 ? ' disabled' : ''),
      onclick: function () {
        if (state.tablePage > 0) { state.tablePage--; renderTable(fs); }
      }
    }, '← Prev'));
    pager.appendChild(el('span', { class: 'pager-info' },
      from + '–' + to + ' / ' + total + ' filmes'
    ));
    pager.appendChild(el('button', {
      class: 'pager-btn' + (state.tablePage >= totalPages - 1 ? ' disabled' : ''),
      onclick: function () {
        if (state.tablePage < totalPages - 1) { state.tablePage++; renderTable(fs); }
      }
    }, 'Next →'));
  }

  /* ---------------- Director / Writer tables ---------------- */
  var PERSON_COLS = [
    { key: 'name',        label: 'Name',          right: false },
    { key: 'gender',      label: 'Gender',         right: false },
    { key: 'nationality', label: 'Nationality',    right: false },
    { key: 'race',        label: 'Race',           right: false },
    { key: 'birthYear',   label: 'Birth Year',     right: true  },
    { key: 'count',       label: 'Movies',         right: true  },
    { key: 'votesImdb',   label: 'Votes IMDB',     right: true  },
    { key: 'votesMl',     label: 'Votes ML',       right: true  },
    { key: 'ratingImdb',  label: 'Avg ★ IMDB', right: true },
    { key: 'ratingMl',    label: 'Avg ★ ML',   right: true },
    { key: 'oscars',      label: 'Oscars',         right: true  },
    { key: 'otherAwards', label: 'Awards',         right: true  }
  ];

  function aggregatePeople(fs, nameKey, personKey) {
    var map = {};
    fs.forEach(function (f) {
      var name = nameKey === 'director' ? f.director : f.wri.name;
      if (!name) return;
      var pid = nameKey === 'director' ? f.directorid : f.wri.id;
      var p = f[personKey];
      var e = map[name] = map[name] || {
        name: name, id: pid, gender: p.gender, nationality: p.country, race: p.race,
        birthYear: null, count: 0,
        votesImdb: 0, votesMl: 0, _rImdb: 0, _rMl: 0,
        oscars: 0, otherAwards: 0
      };
      if (e.birthYear == null && p.age != null && f.year != null) e.birthYear = f.year - p.age;
      e.count++;
      e.votesImdb  += f.votesImdb;
      e.votesMl    += f.votesMl;
      e._rImdb     += f.rating;
      e._rMl       += (f.ratingMl || 0);
      e.oscars     += f.oscars;
      e.otherAwards += f.otherAwards;
    });
    return Object.keys(map).map(function (n) {
      var e = map[n];
      return {
        name: e.name, id: e.id, gender: e.gender, nationality: e.nationality, race: e.race,
        birthYear: e.birthYear,
        count: e.count, votesImdb: e.votesImdb, votesMl: e.votesMl,
        ratingImdb: Math.round(e._rImdb / e.count * 10) / 10,
        ratingMl:   Math.round(e._rMl  / e.count * 10) / 10,
        oscars: e.oscars, otherAwards: e.otherAwards
      };
    });
  }

  function renderPersonTable(data, headId, bodyId, pagerId, sortKeyRef, sortDirRef, pageRef) {
    var sortDir = state[sortDirRef] === 'asc' ? 1 : -1;
    var sorted = data.slice().sort(function (a, b) {
      var av = a[state[sortKeyRef]], bv = b[state[sortKeyRef]];
      if (av == null && bv == null) return 0;
      if (av == null) return 1 * sortDir;
      if (bv == null) return -1 * sortDir;
      if (typeof av === 'string') return av.localeCompare(bv) * sortDir;
      return (av - bv) * sortDir;
    });
    var total = sorted.length;
    var totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    state[pageRef] = Math.min(state[pageRef], totalPages - 1);
    var start = state[pageRef] * PAGE_SIZE;
    var page = sorted.slice(start, start + PAGE_SIZE);

    var head = $(headId); head.innerHTML = '';
    PERSON_COLS.forEach(function (c) {
      var active = state[sortKeyRef] === c.key;
      var arrow = active ? (state[sortDirRef] === 'asc' ? ' ↑' : ' ↓') : '';
      head.appendChild(el('div', {
        class: 'th' + (c.right ? ' right' : '') + (active ? ' active' : ''),
        onclick: function () {
          if (state[sortKeyRef] === c.key) state[sortDirRef] = state[sortDirRef] === 'desc' ? 'asc' : 'desc';
          else { state[sortKeyRef] = c.key; state[sortDirRef] = 'desc'; }
          state[pageRef] = 0;
          renderPersonTable(data, headId, bodyId, pagerId, sortKeyRef, sortDirRef, pageRef);
        }
      }, c.label + arrow));
    });

    var body = $(bodyId); body.innerHTML = '';
    if (!page.length) {
      body.appendChild(el('div', { class: 'empty-row' }, 'No results match the current filters.'));
    } else {
      page.forEach(function (p) {
        body.appendChild(el('div', { class: 'person-trow' }, [
          el('div', { class: 'cell b', title: p.id ? 'ID: ' + p.id : '' }, p.name || '–'),
          el('div', { class: 'cell muted' },          p.gender      || '–'),
          el('div', { class: 'cell muted' },          p.nationality || '–'),
          el('div', { class: 'cell muted' },          p.race        || '–'),
          el('div', { class: 'cell mono right' },     p.birthYear   || '–'),
          el('div', { class: 'cell mono right' },     p.count),
          el('div', { class: 'cell mono right' },     fmtVotes(p.votesImdb)),
          el('div', { class: 'cell mono right' },     p.votesMl ? fmtVotes(p.votesMl) : '–'),
          el('div', { class: 'cell bold right' },     '★ ' + p.ratingImdb.toFixed(1)),
          el('div', { class: 'cell mono right' },     p.ratingMl ? '★ ' + p.ratingMl.toFixed(1) : '–'),
          el('div', { class: 'cell mono right' },     p.oscars      || '–'),
          el('div', { class: 'cell mono right' },     p.otherAwards || '–')
        ]));
      });
    }

    var pager = $(pagerId); pager.innerHTML = '';
    var from = total ? start + 1 : 0, to = Math.min(start + PAGE_SIZE, total);
    pager.appendChild(el('button', {
      class: 'pager-btn' + (state[pageRef] === 0 ? ' disabled' : ''),
      onclick: function () {
        if (state[pageRef] > 0) { state[pageRef]--; renderPersonTable(data, headId, bodyId, pagerId, sortKeyRef, sortDirRef, pageRef); }
      }
    }, '← Prev'));
    pager.appendChild(el('span', { class: 'pager-info' }, from + '–' + to + ' / ' + total + ' pessoas'));
    pager.appendChild(el('button', {
      class: 'pager-btn' + (state[pageRef] >= totalPages - 1 ? ' disabled' : ''),
      onclick: function () {
        if (state[pageRef] < totalPages - 1) { state[pageRef]++; renderPersonTable(data, headId, bodyId, pagerId, sortKeyRef, sortDirRef, pageRef); }
      }
    }, 'Next →'));
  }

  function renderDirTable(fs) {
    var data = aggregatePeople(fs, 'director', 'dir');
    renderPersonTable(data, 'dir-thead', 'dir-tbody', 'dir-tpager', 'dirSortKey', 'dirSortDir', 'dirPage');
  }
  function renderWriTable(fs) {
    var data = aggregatePeople(fs, 'writer', 'wri');
    renderPersonTable(data, 'wri-thead', 'wri-tbody', 'wri-tpager', 'wriSortKey', 'wriSortDir', 'wriPage');
  }

  /* ---------------- Map ---------------- */
  function computeBubbles(fs) {
    var groups = {};
    fs.forEach(function (f) { (groups[f.country] = groups[f.country] || []).push(f); });
    return Object.keys(groups).map(function (c) {
      var list = groups[c];
      var top = list.slice().sort(function (a, b) { return b.rating - a.rating; })[0];
      var avg = list.reduce(function (a, f) { return a + f.rating; }, 0) / list.length;
      return {
        country: c,
        count: list.length,
        votesMl: list.reduce(function (a, f) { return a + f.votesMl; }, 0),
        top: top ? top.title : '—',
        rating: avg.toFixed(1),
        box: fmtMoney(list.reduce(function (a, f) { return a + f.box; }, 0))
      };
    });
  }

  function computeDirBubbles(fs) {
    var groups = {};
    fs.forEach(function (f) {
      var c = f.dir.country || f.country;
      var g = groups[c] = groups[c] || { country: c, count: 0, names: {} };
      g.count++;
      if (f.director) g.names[f.director] = (g.names[f.director] || 0) + 1;
    });
    return Object.keys(groups).map(function (c) {
      var g = groups[c];
      var top = Object.keys(g.names).sort(function (a, b) { return g.names[b] - g.names[a]; })[0] || '—';
      return { country: c, count: g.count, top: top };
    });
  }

  function computeWriBubbles(fs) {
    var groups = {};
    fs.forEach(function (f) {
      var c = f.wri.country || f.country;
      var g = groups[c] = groups[c] || { country: c, count: 0, names: {} };
      g.count++;
      if (f.wri.name) g.names[f.wri.name] = (g.names[f.wri.name] || 0) + 1;
    });
    return Object.keys(groups).map(function (c) {
      var g = groups[c];
      var top = Object.keys(g.names).sort(function (a, b) { return g.names[b] - g.names[a]; })[0] || '—';
      return { country: c, count: g.count, top: top };
    });
  }

  function dirTipFn(entry) {
    return '<div class="tt-title">' + entry.country + '</div>' +
      '<div class="tt-row"><span>Directors</span><b>' + entry.count + '</b></div>' +
      '<div class="tt-top">Notable: ' + entry.top + '</div>';
  }

  function wriTipFn(entry) {
    return '<div class="tt-title">' + entry.country + '</div>' +
      '<div class="tt-row"><span>Writers</span><b>' + entry.count + '</b></div>' +
      '<div class="tt-top">Notable: ' + entry.top + '</div>';
  }

  function ensureMap() {
    var h1 = $('map-holder'), h2 = $('map-holder-votes');
    var h3 = $('map-holder-dir'), h4 = $('map-holder-wri');
    if (!window.d3 || !window.topojson) { setTimeout(ensureMap, 120); return; }
    if (!_ro)  { _ro  = new ResizeObserver(function () { drawMap('map-holder',       'tooltip',       'count',   'films'); }); _ro.observe(h1); }
    if (!_ro2) { _ro2 = new ResizeObserver(function () { drawMap('map-holder-votes', 'tooltip-votes', 'votesMl', 'ML votes', '--map-green', '--map-green-faint'); }); _ro2.observe(h2); }
    if (!_ro3 && h3) { _ro3 = new ResizeObserver(function () { drawMap('map-holder-dir', 'tooltip-dir', 'count', 'directors', '--map-purple', '--map-purple-faint', _dirBubbles, dirTipFn); }); _ro3.observe(h3); }
    if (!_ro4 && h4) { _ro4 = new ResizeObserver(function () { drawMap('map-holder-wri', 'tooltip-wri', 'count', 'writers',   '--map-teal',   '--map-teal-faint',   _wriBubbles, wriTipFn); }); _ro4.observe(h4); }
    if (!_world && !_worldLoading) {
      _worldLoading = true;
      window.dashboardApi.getJson('/static/vendor/countries-110m.json')
        .then(function (r) { return r.json(); })
        .then(function (topo) {
          _world = window.topojson.feature(topo, topo.objects.countries).features;
          drawAllMaps();
        })
        .catch(function () {});
    }
    drawAllMaps();
  }

  function drawAllMaps() {
    drawMap('map-holder',       'tooltip',       'count',   'films');
    drawMap('map-holder-votes', 'tooltip-votes', 'votesMl', 'ML votes', '--map-green',  '--map-green-faint');
    drawMap('map-holder-dir',   'tooltip-dir',   'count',   'directors', '--map-purple', '--map-purple-faint', _dirBubbles, dirTipFn);
    drawMap('map-holder-wri',   'tooltip-wri',   'count',   'writers',   '--map-teal',   '--map-teal-faint',   _wriBubbles, wriTipFn);
  }

  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  function drawMap(holderId, tooltipId, valueKey, maxLabel, colorVar, faintVar, bubblesData, tipFn) {
    var holder = $(holderId);
    if (!holder || !window.d3) return;
    var w = holder.clientWidth, h = holder.clientHeight;
    if (!w || !h) return;
    var d3 = window.d3;
    var accent    = cssVar(colorVar || '--accent') || '#efa838';
    var sphere    = cssVar('--map-sphere');
    var sphereS   = cssVar('--map-sphere-s');
    var grid      = cssVar('--map-grid');
    var empty     = cssVar('--map-empty');
    var border    = cssVar('--map-border');
    var labelClr  = cssVar('--map-label');
    var legendClr = cssVar('--map-legend');
    var accentFaint = cssVar(faintVar || '--map-accent-faint') || 'rgba(239,168,56,.1)';

    holder.innerHTML = '';
    var svg = d3.select(holder).append('svg').attr('width', w).attr('height', h).attr('viewBox', '0 0 ' + w + ' ' + h);
    var projection = d3.geoNaturalEarth1().fitExtent([[14, 14], [w - 14, h - 14]], { type: 'Sphere' });
    var path = d3.geoPath(projection);

    svg.append('path').attr('d', path({ type: 'Sphere' })).attr('fill', sphere).attr('stroke', sphereS).attr('stroke-width', 0.6);
    svg.append('path').attr('d', path(d3.geoGraticule10())).attr('fill', 'none').attr('stroke', grid).attr('stroke-width', 0.5);

    if (!_world) return;

    var data = bubblesData || _bubbles;
    var byName = {};
    data.forEach(function (b) { byName[b.country] = b; });

    var max = d3.max(data, function (b) { return b[valueKey]; }) || 1;
    var colorScale = d3.scaleSequentialSqrt()
      .domain([0, max])
      .interpolator(d3.interpolate(accentFaint, accent));

    var tip = $(tooltipId);

    svg.append('g').selectAll('path')
      .data(_world)
      .join('path')
      .attr('d', path)
      .attr('fill', function (d) {
        var name = ISO_NUM[+d.id];
        var entry = name ? byName[name] : null;
        return entry ? colorScale(entry[valueKey]) : empty;
      })
      .attr('stroke', border)
      .attr('stroke-width', 0.4)
      .style('cursor', function (d) { return ISO_NUM[+d.id] && byName[ISO_NUM[+d.id]] ? 'pointer' : 'default'; })
      .on('mousemove', function (event, d) {
        var name = ISO_NUM[+d.id];
        var entry = name ? byName[name] : null;
        if (!entry) { tip.style.display = 'none'; return; }
        var p = d3.pointer(event, holder);
        tip.style.display = 'block';
        tip.style.left = p[0] + 'px'; tip.style.top = p[1] + 'px'; tip.style.transform = 'translate(14px,-50%)';
        tip.innerHTML = tipFn ? tipFn(entry) :
          '<div class="tt-title">' + entry.country + '</div>' +
          '<div class="tt-row"><span>Films</span><b>' + entry.count + '</b></div>' +
          '<div class="tt-row"><span>ML votes</span><b>' + fmtVotes(entry.votesMl) + '</b></div>' +
          '<div class="tt-row"><span>Avg rating</span><b>★ ' + entry.rating + '</b></div>' +
          '<div class="tt-row"><span>Box office</span><b>' + entry.box + '</b></div>' +
          '<div class="tt-top">Top: ' + entry.top + '</div>';
      })
      .on('mouseleave', function () { tip.style.display = 'none'; });

    // Continent labels
    var labels = [['NORTH AMERICA', -100, 47], ['SOUTH AMERICA', -58, -13], ['EUROPE', 13, 52], ['AFRICA', 20, 4], ['ASIA', 95, 46], ['OCEANIA', 134, -26]];
    svg.append('g').selectAll('text').data(labels).join('text')
      .attr('transform', function (d) { var p = projection([d[1], d[2]]); return 'translate(' + p[0] + ',' + p[1] + ')'; })
      .text(function (d) { return d[0]; }).attr('text-anchor', 'middle').attr('dy', '0.3em')
      .attr('fill', labelClr).attr('font-size', 10).attr('letter-spacing', 2.5)
      .attr('font-family', 'JetBrains Mono, monospace').style('pointer-events', 'none');

    // Color legend
    var gradId = 'choro-grad-' + holderId;
    var lw = 120, lh = 8, lx = w - lw - 16, ly = h - 24;
    var defs = svg.append('defs');
    var grad = defs.append('linearGradient').attr('id', gradId);
    grad.append('stop').attr('offset', '0%').attr('stop-color', accentFaint);
    grad.append('stop').attr('offset', '100%').attr('stop-color', accent);
    var lg = svg.append('g').attr('transform', 'translate(' + lx + ',' + ly + ')');
    lg.append('rect').attr('width', lw).attr('height', lh).attr('rx', 2).attr('fill', 'url(#' + gradId + ')').attr('opacity', 0.9);
    lg.append('text').attr('x', 0).attr('y', lh + 11).attr('fill', legendClr).attr('font-size', 9).attr('font-family', 'JetBrains Mono, monospace').text('0');
    lg.append('text').attr('x', lw).attr('y', lh + 11).attr('text-anchor', 'end').attr('fill', legendClr).attr('font-size', 9).attr('font-family', 'JetBrains Mono, monospace').text(fmtVotes(max) + ' ' + maxLabel);
  }

  /* ---------------- Tabs & init ---------------- */
  function setTab(tab) {
    var prevTab = state.tab;
    state.tab = tab;
    var topbarMenu = $('topbar-menu');
    if (topbarMenu) topbarMenu.classList.remove('open');
    var menuToggleBtn = $('menu-toggle-btn');
    if (menuToggleBtn) menuToggleBtn.setAttribute('aria-expanded', 'false');
    Array.prototype.forEach.call(document.querySelectorAll('.tab'), function (b) {
      var active = b.getAttribute('data-tab') === tab;
      b.classList.toggle('active', active);
      b.setAttribute('role', 'tab');
      b.setAttribute('aria-selected', active ? 'true' : 'false');
      b.setAttribute('tabindex', active ? '0' : '-1');
    });
    $('pane-bilheteria').classList.toggle('active', tab === 'bilheteria');
    $('pane-filmes').classList.toggle('active', tab === 'filmes');
    $('pane-diretores').classList.toggle('active', tab === 'diretores');
    $('pane-produtores').classList.toggle('active', tab === 'produtores');
    $('pane-paises').classList.toggle('active', tab === 'paises');
    $('pane-salaexibicao').classList.toggle('active', tab === 'salaexibicao');
    $('pane-requerente').classList.toggle('active', tab === 'requerente');
    $('pane-chat').classList.toggle('active', tab === 'chat');
    var aiBtn = $('ai-chat-btn');
    if (aiBtn) aiBtn.classList.toggle('active', tab === 'chat');
    // Carga dos dados da aba: feita em render() (chamado logo abaixo), que só
    // busca de novo se os filtros mudaram desde a última carga (loadedQs) —
    // evita refazer a consulta ao só trocar de aba sem alterar filtro.
    if (tab === 'chat') loadChatModels();
    // painel lateral: entra/sai do modo chat sem perder a seleção normal
    // (filme/pessoa/sala) de "Detalhes do Filme" ao alternar entre as outras abas
    if (tab === 'chat') renderChatAside();
    else if (prevTab === 'chat') renderDetailAside();
    render();
  }

  var SUN_SVG = '<path d="M12 4.5V3m0 18v-1.5M4.5 12H3m18 0h-1.5M6.34 6.34 5.28 5.28m13.44 13.44-1.06-1.06M6.34 17.66l-1.06 1.06M18.72 5.28l-1.06 1.06"/><circle cx="12" cy="12" r="4"/>';
  var MOON_SVG = '<path d="M21 12.79A9 9 0 1 1 11.21 3a7 7 0 0 0 9.79 9.79z"/>';

  function applyTheme(dark) {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    var icon = $('theme-icon');
    if (icon) icon.innerHTML = dark ? MOON_SVG : SUN_SVG;
  }

  function init() {
    restoreStateFromUrl();
    window.addEventListener('dashboard-api-error', showApiError);
    // Theme toggle
    var isDark = document.documentElement.getAttribute('data-theme') !== 'light';
    applyTheme(isDark);
    $('theme-btn').addEventListener('click', function () {
      isDark = !isDark;
      localStorage.setItem('bilheteria-theme', isDark ? 'dark' : 'light');
      applyTheme(isDark);
    });

    buildSidebar();
    var sidebarToggle = $('sidebar-toggle');
    if (sidebarToggle) {
      sidebarToggle.addEventListener('click', function () {
        $('sidebar-aside').classList.toggle('collapsed');
      });
    }
    var detailToggle = $('detail-toggle');
    if (detailToggle) {
      detailToggle.addEventListener('click', function () {
        state.detailAsideOpen = !state.detailAsideOpen;
        $('detail-aside').classList.toggle('collapsed', !state.detailAsideOpen);
      });
    }

    // Menu mobile (hamburger com as abas + "Pesquisar com IA")
    var menuToggleBtn = $('menu-toggle-btn');
    var topbarMenu = $('topbar-menu');
    if (menuToggleBtn && topbarMenu) {
      menuToggleBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        var open = topbarMenu.classList.toggle('open');
        menuToggleBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
      document.addEventListener('click', function (e) {
        if (!topbarMenu.classList.contains('open')) return;
        if (topbarMenu.contains(e.target) || menuToggleBtn.contains(e.target)) return;
        topbarMenu.classList.remove('open');
        menuToggleBtn.setAttribute('aria-expanded', 'false');
      });
    }
    // No celular, sidebar de filtros e painel de detalhes começam
    // recolhidos (a área central ocupa a tela inteira) — no desktop
    // ambos começam abertos, como sempre.
    if (window.matchMedia && window.matchMedia('(max-width: 768px)').matches) {
      $('sidebar-aside').classList.add('collapsed');
      state.detailAsideOpen = false;
      $('detail-aside').classList.add('collapsed');
    }

    renderDetailAside();
    Array.prototype.forEach.call(document.querySelectorAll('.tab'), function (b) {
      b.addEventListener('click', function () { setTab(b.getAttribute('data-tab')); });
    });
    var aiChatBtn = $('ai-chat-btn');
    if (aiChatBtn) {
      aiChatBtn.addEventListener('click', function () { setTab(state.tab === 'chat' ? 'bilheteria' : 'chat'); });
    }
    $('clear-btn').addEventListener('click', function () {
      ['anos','paisOrigem','grupoExibidor','municipioSala','ufSala','municipioRequerente','ufRequerente'].forEach(function (k) { state[k] = []; });
      ['semanaInicio','semanaFim','cpbRoe','tituloBrasileiro','tituloOriginal','registroSala','nomeDiretor','nomeProdutor','cnpjRequerente','nomeRequerente'].forEach(function (k) {
        state[k] = '';
        var inp = $('search-' + k); if (inp) inp.value = '';
      });
      render();
    });
    setTab(state.tab);
  }

  function loadAndInit() {
    var overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(10,14,26,0.9);display:flex;align-items:center;justify-content:center;z-index:9999;flex-direction:column;gap:14px;';
    var msg = document.createElement('div');
    msg.style.cssText = 'color:#efa838;font-family:JetBrains Mono,monospace;font-size:13px;letter-spacing:2px;';
    msg.textContent = 'CARREGANDO BASE DE DADOS…';
    var dots = document.createElement('div');
    dots.style.cssText = 'color:rgba(239,168,56,0.4);font-family:JetBrains Mono,monospace;font-size:11px;letter-spacing:1px;';
    dots.textContent = 'connecting to oracle';
    overlay.appendChild(msg);
    document.body.appendChild(overlay);
    announce('Carregando base de dados.');

    Promise.all([
      window.dashboardApi.getJson('/api/films'),
      window.dashboardApi.getJson('/api/ratings-dist')
    ])
      .then(function(results) {
        var data = results[0];
        RATINGS_DIST = results[1];
        FILMS = data;
        YEARS = Array.from(
          new Set(FILMS.map(function(f) { return f.year; }).filter(function(y) { return y != null; }))
        ).sort(function(a, b) { return a - b; });

        // Genres from real data (sorted), fall back to the hardcoded lists
        var mlGs = uniqSort(FILMS.map(function(f) { return f.mlGenre; }).filter(Boolean));
        var imGs = uniqSort(FILMS.map(function(f) { return f.imdbGenre; }).filter(Boolean));
        if (mlGs.length) ML_GENRES = mlGs;
        if (imGs.length) IMDB_GENRES = imGs;

        // Continent/region/country from real data; fall back to country-data.js
        var rows = window.CINEMAP_COUNTRY_ROWS || [];
        var derivedConts = uniqSort(FILMS.map(function(f) { return f.continent; }).filter(function(x) { return x && x !== 'Other'; }));
        var derivedRegs  = uniqSort(FILMS.map(function(f) { return f.region; }).filter(Boolean));
        var derivedCntrs = uniqSort(FILMS.map(function(f) { return f.country; }).filter(function(x) { return x && x !== 'Unknown'; }));
        OD = {
          conts:     derivedConts.length ? derivedConts : uniqSort(rows.map(function(r) { return r[1]; })),
          regs:      derivedRegs.length  ? derivedRegs  : uniqSort(rows.map(function(r) { return r[2]; })),
          countries: derivedCntrs.length ? derivedCntrs : rows.map(function(r) { return r[0]; }).sort(function(a, b) { return a.localeCompare(b); })
        };
        document.body.removeChild(overlay);
        announce('Painel carregado.');
        init();
        loadPeriodoOptions();
        loadObraOptions();
        loadSalaOptions();
      })
      .catch(function(err) {
        msg.textContent = 'ERRO: servidor não disponível';
        dots.textContent = 'inicie com: uv run uvicorn server:app --reload';
        msg.style.color = '#ef5b5b';
        announce('Erro ao carregar o painel.');
        console.error('[BilheteriaBR] failed to load films:', err);
      });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', loadAndInit);
  else loadAndInit();
})();
