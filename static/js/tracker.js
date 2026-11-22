/*
 * Suivi comportemental en temps réel (page leçon).
 * Envoie au serveur (api/suivi/) :
 *   TEMPS      : secondes d'activité réelle (toutes les 15 s et à la fermeture)
 *   CLIC       : nombre de clics (par paquets)
 *   INACTIVITE : durée d'une période sans interaction >= seuil
 * Le temps ne compte que si l'onglet est visible et que l'utilisateur interagit.
 */
(function () {
  var cfg = document.getElementById('tracker-config');
  if (!cfg) return;

  var leconId = cfg.dataset.lecon;
  var url = cfg.dataset.url;
  var seuil = parseInt(cfg.dataset.seuil, 10) || 60;
  var csrf = cfg.dataset.csrf;

  var actif = 0;          // secondes actives cumulées
  var envoye = 0;         // secondes déjà envoyées
  var clics = 0;
  var derniereActivite = Date.now();

  function envoyer(type, duree) {
    try {
      fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
        body: JSON.stringify({lecon_id: leconId, type: type, duree: duree}),
        keepalive: true
      }).catch(function () {});
    } catch (e) {}
  }

  function signalerInactivite() {
    var inactif = (Date.now() - derniereActivite) / 1000;
    if (inactif >= seuil) {
      envoyer('INACTIVITE', Math.round(inactif));
      derniereActivite = Date.now();
    }
  }

  function surActivite(e) {
    signalerInactivite();          // si on revient après une longue pause
    derniereActivite = Date.now();
    if (e.type === 'click') clics++;
  }

  ['mousemove', 'keydown', 'scroll', 'click', 'touchstart'].forEach(function (ev) {
    document.addEventListener(ev, surActivite, {passive: true});
  });

  setInterval(function () {
    var inactif = (Date.now() - derniereActivite) / 1000;
    if (!document.hidden && inactif < seuil) actif++;
  }, 1000);

  function vider() {
    var delta = actif - envoye;
    if (delta > 0) { envoyer('TEMPS', delta); envoye = actif; }
    if (clics > 0) { envoyer('CLIC', clics); clics = 0; }
  }

  setInterval(vider, 15000);
  window.addEventListener('pagehide', function () { signalerInactivite(); vider(); });
  document.addEventListener('visibilitychange', function () { if (document.hidden) vider(); });
})();
