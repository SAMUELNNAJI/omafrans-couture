/**
 * dressing-room.js — Omafrans Couture AI Dressing Room
 */
(function () {
  'use strict';

  if (!document.getElementById('roomFile')) return;

  var API_URL = window.DR_GENERATE_URL || '/api/dressing-room/generate/';
  console.log('[DR] API:', API_URL);

  /* ── elements ─────────────────────────────────────────────────── */
  var elFile        = document.getElementById('roomFile');
  var elThumb       = document.getElementById('roomThumb');
  var elFigure      = document.getElementById('figure');
  var elFitBox      = document.getElementById('fitBox');
  var elCanvas      = document.getElementById('canvas');
  var elGenerated   = document.getElementById('generatedPreview');
  var elPreviewPlaceholder = document.getElementById('roomPreviewPlaceholder');
  var elThreeMount  = document.getElementById('threeMount');
  var elViews       = document.getElementById('roomViews');
  var elStatus      = document.getElementById('roomStatus');
  var elGenerate    = document.getElementById('generateLook');
  var elContact     = document.getElementById('roomContact');
  var elNotes       = document.getElementById('designNotes');
  var elSizeButtons = document.getElementById('roomSizes');
  var elSizeInfo    = document.getElementById('sizeInfo');
  var elFabrics     = document.getElementById('fabrics');
  var elPalettes    = document.getElementById('palettes');
  var elPalNav      = document.getElementById('palNav');
  var elZoomIn      = document.getElementById('zoomIn');
  var elZoomOut     = document.getElementById('zoomOut');
  var elReset       = document.getElementById('roomReset');
  var elToolMove    = document.getElementById('toolMove');
  var elToolColor   = document.getElementById('toolColor');
  var elOverlay     = document.getElementById('roomLoadingOverlay');
  var elOverlayText = document.getElementById('roomLoadingText');
  var elDragHint    = document.getElementById('roomDragHint') || document.querySelector('.room-drag-hint');

  /* ── colour tone → THREE.Color map ───────────────────────────── */
  /* Each entry is [r, g, b] multiplier (1 = original) */
  var COLOUR_TO_THREE = {
    'none':                                                   [1,    1,    1   ],
    'grayscale(1) brightness(1.9)':                           [1.9,  1.9,  1.9 ],  // ivory — brighten + desaturate handled below
    'grayscale(1) brightness(1.2)':                           [1.2,  1.2,  1.2 ],  // stone
    'grayscale(1) brightness(.7)':                            [0.7,  0.7,  0.7 ],  // charcoal
    'grayscale(1) brightness(.35)':                           [0.35, 0.35, 0.35],  // black
    'sepia(1) brightness(1.5) saturate(.8)':                  [1.6,  1.3,  0.85],  // sand
    'sepia(1) brightness(1.1) saturate(1.6)':                 [1.4,  1.05, 0.6 ],  // camel
    'sepia(1) hue-rotate(-20deg) saturate(2) brightness(.8)': [1.2,  0.6,  0.3 ],  // rust
    'sepia(1) brightness(.6) saturate(1.2)':                  [0.7,  0.4,  0.2 ],  // brown
    'sepia(1) hue-rotate(30deg) brightness(.7) saturate(1.4)':[0.65, 0.72, 0.28],  // olive
    'hue-rotate(-60deg) saturate(1.5)':                       [1.0,  0.2,  0.6 ],  // wine
    'hue-rotate(60deg) saturate(1.6) brightness(.9)':         [0.2,  0.3,  1.1 ],  // navy
    'hue-rotate(150deg) saturate(1.4) brightness(.8)':        [0.2,  0.8,  0.35],  // forest
    'hue-rotate(-30deg) saturate(2)':                         [1.5,  0.1,  0.25],  // crimson
    'hue-rotate(90deg) saturate(1.2) brightness(1.2)':        [0.6,  1.3,  1.7 ],  // sky
    'hue-rotate(120deg) saturate(1.2)':                       [0.4,  0.75, 1.3 ],  // steel
    'hue-rotate(170deg) saturate(1.3)':                       [0.2,  1.1,  1.1 ],  // teal
    'hue-rotate(40deg) saturate(1.1) brightness(1.3)':        [1.3,  1.1,  1.7 ],  // lavender
    'hue-rotate(200deg) saturate(1.3) brightness(1.1)':       [0.7,  1.6,  1.25],  // mint
  };
  /* Grayscale flag for entries that need desaturation */
  var GRAYSCALE_KEYS = [
    'grayscale(1) brightness(1.9)',
    'grayscale(1) brightness(1.2)',
    'grayscale(1) brightness(.7)',
    'grayscale(1) brightness(.35)',
  ];

  /* ── state ────────────────────────────────────────────────────── */
  var S = {
    file:         null,
    sourceUrl:    '',
    generatedUrl: '',
    sizeName:     'M',
    sizeMeasure:  'Bust 90 · Waist 72 · Hips 96',
    fabric:       'Premium Gabardine',
    colour:       'none',
    view:         'front',
    zoom:         1,
    rotY:         0,
    rotX:         0,
    x:            0,
    y:            0,
    hasResult:    false,
    busy:         false,
    lastNotes:    '',
  };

  var SIZE_SCALE_2D = { XS:.84, S:.92, M:1, L:1.08, XL:1.17, '2XL':1.27, '3XL':1.40, '4XL':1.55, '5XL':1.70 };

  /* ── status ───────────────────────────────────────────────────── */
  function setStatus(msg, type) {
    elStatus.textContent = msg;
    elStatus.className = 'room-status' + (type ? ' room-status--' + type : '');
  }

  function showLoading(msg) {
    if (elOverlayText) elOverlayText.textContent = msg || 'Generating…';
    if (elOverlay) { elOverlay.hidden = false; elOverlay.style.display = 'flex'; }
  }

  function hideLoading() {
    if (elOverlay) { elOverlay.hidden = true; elOverlay.style.display = 'none'; }
  }

  /* ── 2-D fallback paint ───────────────────────────────────────── */
  function paint2D() {
    var sc = SIZE_SCALE_2D[S.sizeName] || 1;
    if (elFitBox) elFitBox.style.transform = 'scaleX(' + sc + ')';
    if (elFigure) elFigure.style.transform =
      'translate(' + S.x + 'px,' + S.y + 'px) scale(' + S.zoom + ')';
    if (elGenerated) elGenerated.style.transform =
      'translate(' + S.x + 'px,' + S.y + 'px) scale(' + S.zoom + ')';
  }

  /* ── Three.js ─────────────────────────────────────────────────── */
  var T3 = null;   // { renderer, scene, bgScene, camera, mesh, mat, bgMesh }

  function initThree() {
    if (!window.THREE || !elThreeMount || T3) return;
    try {
      var W = elThreeMount.clientWidth  || 600;
      var H = elThreeMount.clientHeight || 520;

      var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
      renderer.setSize(W, H);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setClearColor(0x000000, 1);
      renderer.autoClear = false;
      elThreeMount.innerHTML = '';
      elThreeMount.appendChild(renderer.domElement);

      /* ── background scene (never rotates) ── */
      var bgScene  = new THREE.Scene();
      var bgCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
      var bgTex    = _makeBgTexture();
      var bgMesh   = new THREE.Mesh(
        new THREE.PlaneGeometry(2, 2),
        new THREE.MeshBasicMaterial({ map: bgTex, depthTest: false })
      );
      bgScene.add(bgMesh);

      /* ── foreground scene (model mesh rotates) ── */
      var scene  = new THREE.Scene();
      var camera = new THREE.PerspectiveCamera(38, W / H, 0.1, 100);
      camera.position.z = 2.8;

      var keyLight  = new THREE.DirectionalLight(0xfff4e0, 1.6);
      keyLight.position.set(-1.5, 2.5, 3);
      scene.add(keyLight);
      var fillLight = new THREE.DirectionalLight(0xdde8ff, 0.7);
      fillLight.position.set(2, 0.5, 1);
      scene.add(fillLight);
      scene.add(new THREE.AmbientLight(0xffffff, 0.9));

      /* ── model plane ── */
      var mat  = new THREE.MeshStandardMaterial({
        color:       0xffffff,
        side:        THREE.FrontSide,
        transparent: true,
        roughness:   0.55,
        metalness:   0.0,
      });
      var mesh = new THREE.Mesh(new THREE.PlaneGeometry(1.55, 2.07), mat);
      scene.add(mesh);

      /* ── shadow plane under model ── */
      var shadowMat  = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.12 });
      var shadowMesh = new THREE.Mesh(new THREE.EllipseCurve ? new THREE.CircleGeometry(0.5, 32) : new THREE.PlaneGeometry(1.0, 0.18), shadowMat);
      shadowMesh.position.set(0, -1.08, -0.01);
      shadowMesh.rotation.x = -Math.PI / 2.2;
      scene.add(shadowMesh);

      T3 = { renderer: renderer, bgScene: bgScene, bgCamera: bgCamera,
              scene: scene, camera: camera, mesh: mesh, mat: mat };

      /* ── render loop ── */
      (function loop() {
        T3.raf = requestAnimationFrame(loop);
        renderer.clear();
        renderer.render(bgScene, bgCamera);       // draw fixed background
        renderer.clearDepth();
        renderer.render(scene, camera);            // draw rotating model on top
      })();

      /* ── resize observer ── */
      if (window.ResizeObserver) {
        new ResizeObserver(function () {
          var w = elThreeMount.clientWidth, h = elThreeMount.clientHeight;
          if (!w || !h) return;
          renderer.setSize(w, h);
          camera.aspect = w / h;
          camera.updateProjectionMatrix();
        }).observe(elThreeMount);
      }

      console.log('[DR] Three.js ready — separate bg + model scenes');
    } catch (err) {
      console.error('[DR] Three.js init failed:', err);
      T3 = null;
    }
  }

  /* Generate a lightweight room background texture via canvas */
  function _makeBgTexture() {
    var c = document.createElement('canvas');
    c.width = 512; c.height = 512;
    var ctx = c.getContext('2d');

    // Cream wall
    var wallGrad = ctx.createLinearGradient(0, 0, 0, 370);
    wallGrad.addColorStop(0,   '#ede5d8');
    wallGrad.addColorStop(1,   '#d8ccbc');
    ctx.fillStyle = wallGrad;
    ctx.fillRect(0, 0, 512, 370);

    // Subtle panel lines
    ctx.strokeStyle = 'rgba(180,168,150,0.5)';
    ctx.lineWidth = 1.5;
    [85, 256, 427].forEach(function(cx) {
      ctx.strokeRect(cx - 60, 20, 120, 330);
    });

    // Warm parquet floor
    var floorGrad = ctx.createLinearGradient(0, 370, 0, 512);
    floorGrad.addColorStop(0, '#c8a878');
    floorGrad.addColorStop(1, '#b8946a');
    ctx.fillStyle = floorGrad;
    ctx.fillRect(0, 370, 512, 142);

    // Floor planks
    ctx.strokeStyle = 'rgba(148,118,82,0.5)';
    ctx.lineWidth = 1;
    for (var y = 370; y < 512; y += 24) { ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(512,y); ctx.stroke(); }

    // Soft spotlight
    var spot = ctx.createRadialGradient(256, 0, 20, 256, 100, 300);
    spot.addColorStop(0,   'rgba(255,248,225,0.35)');
    spot.addColorStop(1,   'rgba(255,248,225,0)');
    ctx.fillStyle = spot;
    ctx.fillRect(0, 0, 512, 512);

    if (THREE.CanvasTexture) return new THREE.CanvasTexture(c);
    var t = new THREE.Texture(c);
    t.needsUpdate = true;
    return t;
  }

  function applyRot() {
    if (!T3) return;
    T3.mesh.rotation.y = S.rotY * Math.PI / 180;
    T3.mesh.rotation.x = S.rotX * Math.PI / 180;
  }

  /* Apply colour tone to the Three.js mesh material color (not CSS filter) */
  function applyColourToMesh() {
    if (!T3 || !window.THREE) return;
    var rgb = COLOUR_TO_THREE[S.colour] || [1, 1, 1];
    var isGray = GRAYSCALE_KEYS.indexOf(S.colour) !== -1;

    if (isGray) {
      /* For grayscale tones use a THREE.Color desaturation via shader trick —
         we use a greyscale by setting color channels equally */
      var v = rgb[0];
      T3.mat.color.setRGB(v, v, v);
    } else {
      T3.mat.color.setRGB(
        Math.min(rgb[0], 2),
        Math.min(rgb[1], 2),
        Math.min(rgb[2], 2)
      );
    }
    T3.mat.needsUpdate = true;
  }

  function loadTex(dataUrl, callback) {
    if (!T3) { if (callback) callback(false); return; }
    new THREE.TextureLoader().load(dataUrl, function (tex) {
      if (THREE.SRGBColorSpace !== undefined)  tex.colorSpace = THREE.SRGBColorSpace;
      else if (THREE.sRGBEncoding !== undefined) tex.encoding = THREE.sRGBEncoding;
      T3.mat.map = tex;
      T3.mat.needsUpdate = true;
      applyRot();
      applyColourToMesh();
      console.log('[DR] Texture loaded into 3D mesh');
      if (callback) callback(true);
    }, undefined, function (err) {
      console.warn('[DR] Texture load error:', err);
      if (callback) callback(false);
    });
  }

  /* ── show/hide helpers ─────────────────────────────────────────── */
  function show3D() {
    if (elFigure)     { elFigure.hidden = true;     elFigure.style.display = 'none'; }
    if (elThreeMount) { elThreeMount.hidden = false; elThreeMount.style.display = 'block'; }
    if (elDragHint)   { elDragHint.hidden = false;   elDragHint.style.display = 'flex'; }
    elCanvas.classList.add('mode-3d');
  }

  function showPreviewPlaceholder(message) {
    if (elFigure)     { elFigure.hidden = false; elFigure.style.display = ''; }
    if (elThreeMount) { elThreeMount.hidden = true; elThreeMount.style.display = 'none'; }
    if (elGenerated)  { elGenerated.hidden = true; elGenerated.style.display = 'none'; }
    if (elDragHint)   { elDragHint.hidden = true;   elDragHint.style.display = 'none'; }
    if (elPreviewPlaceholder) {
      elPreviewPlaceholder.hidden = false;
      elPreviewPlaceholder.textContent = message;
    }
    elCanvas.classList.remove('mode-3d');
  }

  function showGenerated() {
    if (elFigure)     { elFigure.hidden = true; elFigure.style.display = 'none'; }
    if (elThreeMount) { elThreeMount.hidden = true; elThreeMount.style.display = 'none'; }
    if (elGenerated)  { elGenerated.hidden = false; elGenerated.style.display = 'block'; }
    if (elPreviewPlaceholder) elPreviewPlaceholder.hidden = true;
    if (elDragHint)   { elDragHint.hidden = true;   elDragHint.style.display = 'none'; }
    elCanvas.classList.remove('mode-3d');
  }

  /* ── file load ─────────────────────────────────────────────────── */
  function loadFile(file) {
    if (!file) return;
    if (!file.type.startsWith('image/')) { setStatus('Please choose an image file.', 'warn'); return; }
    if (file.size > 12 * 1024 * 1024)   { setStatus('Image too large (max 12 MB).', 'warn'); return; }

    if (S.sourceUrl)    URL.revokeObjectURL(S.sourceUrl);
    if (S.generatedUrl) URL.revokeObjectURL(S.generatedUrl);
    S.file = file; S.sourceUrl = URL.createObjectURL(file);
    S.generatedUrl = ''; S.hasResult = false;

    elThumb.src   = S.sourceUrl;
    showPreviewPlaceholder('Generating an AI fitting from your upload. The original photo remains in the thumbnail.');

    elContact.disabled     = true;
    elGenerate.disabled    = false;
    elGenerate.textContent = 'Generate preview';
    S.x = S.y = S.rotX = S.rotY = 0;
    S.view = 'front';
    if (elViews) elViews.querySelectorAll('button').forEach(function (b) {
      var selected = b.dataset.view === S.view;
      b.classList.toggle('on', selected);
      b.setAttribute('aria-pressed', selected ? 'true' : 'false');
    });
    paint2D();
    setStatus('Dress loaded. Generating AI preview…');
    console.log('[DR] File loaded:', file.name, file.size);
    _autoGenDebounce(150);
  }

  elFile.addEventListener('change', function (e) { loadFile(e.target.files[0]); });

  /* Drag-and-drop on file box */
  var elFileBox = document.getElementById('fileBoxDrop') || (elThumb && elThumb.closest('.file-box'));
  if (elFileBox) {
    elFileBox.addEventListener('click', function (e) { if (e.target !== elFile) elFile.click(); });
    elFileBox.addEventListener('dragover', function (e) { e.preventDefault(); elFileBox.classList.add('drag-hover'); });
    elFileBox.addEventListener('dragleave', function () { elFileBox.classList.remove('drag-hover'); });
    elFileBox.addEventListener('drop', function (e) {
      e.preventDefault(); elFileBox.classList.remove('drag-hover');
      if (e.dataTransfer && e.dataTransfer.files[0]) loadFile(e.dataTransfer.files[0]);
    });
  }

  /* Collection "try it on" */
  function loadCollectionDress() {
    var imageUrl = document.body.dataset.tryOnImage;
    if (!imageUrl) return;
    setStatus('Loading collection dress…');
    fetch(imageUrl).then(function (r) { return r.blob(); }).then(function (blob) {
      var ext = blob.type === 'image/jpeg' ? 'jpg' : 'png';
      loadFile(new File([blob], 'collection-dress.' + ext, { type: blob.type }));
    }).catch(function () { setStatus('Could not load collection dress. Upload manually.', 'warn'); });
  }

  /* ── generate ──────────────────────────────────────────────────── */
  var _activeCtrl = null;
  var _genTimer   = null;

  function _autoGenDebounce(ms) {
    if (_genTimer) clearTimeout(_genTimer);
    _genTimer = setTimeout(function () {
      if (S.file) triggerGenerate();
    }, ms || 200);
  }

  function triggerGenerate() {
    if (!S.file) { setStatus('Upload a dress photo first.', 'warn'); elFile.focus(); return; }
    if (S.busy) {
      if (_activeCtrl) try { _activeCtrl.abort(); } catch(_) {}
      S.busy = false;
    }

    S.busy = true;
    elGenerate.disabled    = true;
    elGenerate.textContent = 'Generating…';
    elContact.disabled     = true;
    showLoading('Generating a ' + S.view + ' view for size ' + S.sizeName + '…');
    setStatus('');

    var fd = new FormData();
    fd.append('dress',   S.file);
    fd.append('size',    S.sizeName);
    fd.append('fabric',  S.fabric);
    fd.append('colour',  S.colour);
    fd.append('view',    S.view);
    var notesVal = (elNotes.value || '').trim().slice(0, 500);
    S.lastNotes = notesVal;
    fd.append('notes', notesVal);

    console.log('[DR] POST', API_URL, 'size:', S.sizeName, 'fabric:', S.fabric, 'colour:', S.colour);

    var ctrl = new AbortController();
    _activeCtrl = ctrl;
    var tID = setTimeout(function () { ctrl.abort(); }, 90000);

    fetch(API_URL, { method: 'POST', body: fd, signal: ctrl.signal })
      .then(function (res) { return res.text().then(function (t) { return { s: res.status, t: t }; }); })
      .then(function (obj) {
        clearTimeout(tID); _activeCtrl = null;
        console.log('[DR] Response', obj.s, '— first 120:', obj.t.slice(0, 120));

        var data;
        try { data = JSON.parse(obj.t); } catch (_) {
          throw new Error('Non-JSON (' + obj.s + '): ' + obj.t.slice(0, 80));
        }
        if (obj.s !== 200 || data.error) throw new Error(data.error || 'Server error ' + obj.s);

        /* decode base64 PNG */
        var b64 = data.image, bin = atob(b64), arr = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
        var blob = new Blob([arr], { type: 'image/png' });
        if (S.generatedUrl) URL.revokeObjectURL(S.generatedUrl);
        S.generatedUrl = URL.createObjectURL(blob);
        S.hasResult    = true;
        S.busy         = false;

        console.log('[DR] Decoded blob', blob.size, 'bytes. is_ai:', data.is_ai);

        elGenerated.src = S.generatedUrl;
        elGenerated.alt = 'AI-generated ' + S.view + ' view of the fitting';
        showGenerated();
        _finishGenerate(data.is_ai);

        setTimeout(hideLoading, 1000); // safety
      })
      .catch(function (err) {
        clearTimeout(tID);
        if (err.name === 'AbortError' && _activeCtrl !== ctrl) {
          console.log('[DR] Superseded generation aborted');
          return;
        }
        _activeCtrl = null; S.busy = false;
        hideLoading();
        elGenerate.disabled    = false;
        elGenerate.textContent = 'Try again';
        if (!S.hasResult) {
          var reason = err.name === 'AbortError' ? 'Generation timed out. Please try again.' : err.message;
          showPreviewPlaceholder('No AI fitting was generated. Your upload is shown only in the thumbnail. ' + reason);
        }
        setStatus(err.name === 'AbortError' ? 'Generation timed out. Please try again.' : err.message, 'error');
        console.error('[DR] Generate error:', err);
      });
  }

  function _finishGenerate(isAi) {
    hideLoading();
    elContact.disabled     = false;
    elGenerate.disabled    = false;
    elGenerate.textContent = 'Regenerate';
    setStatus(
      isAi
        ? 'AI ' + S.view + ' view ready. Choose another angle or change colour/fabric to generate an updated preview.'
        : 'Preview ready. Choose another angle or change colour/fabric to generate an updated preview.',
      'ok'
    );
  }

  elGenerate.addEventListener('click', triggerGenerate);

  /* ── size buttons ──────────────────────────────────────────────── */
  elSizeButtons.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    elSizeButtons.querySelectorAll('button').forEach(function (x) { x.classList.remove('on'); });
    b.classList.add('on');
    S.sizeName    = b.dataset.size || b.textContent.trim();
    S.sizeMeasure = b.dataset.m || '';
    elSizeInfo.textContent = 'Size ' + S.sizeName
      + (b.dataset.label ? ' · ' + b.dataset.label : '')
      + ' · ' + S.sizeMeasure + ' cm';
    paint2D();
    if (S.file) { setStatus('Size ' + S.sizeName + ' — regenerating…'); _autoGenDebounce(200); }
  });

  /* ── fabric buttons ────────────────────────────────────────────── */
  elFabrics.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    elFabrics.querySelectorAll('button').forEach(function (x) { x.classList.remove('on'); });
    b.classList.add('on');
    S.fabric = b.textContent.trim();
    if (S.file) { setStatus('Fabric: ' + S.fabric + ' — generating updated preview…'); _autoGenDebounce(300); }
    else setStatus('Fabric selected. Upload a garment photo to see it in a generated preview.');
  });

  /* ── colour palette ────────────────────────────────────────────── */
  elPalettes.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    elPalettes.querySelectorAll('button').forEach(function (x) { x.classList.remove('on'); });
    b.classList.add('on');
    S.colour = b.dataset.f || 'none';
    var label = b.getAttribute('aria-label') || 'selected';
    if (S.file) {
      setStatus('Generating the garment in ' + label + '…');
      _autoGenDebounce(200);
    } else {
      setStatus('Colour selected. Upload a garment photo to generate a preview in this tone.');
    }
  });

  elPalNav.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    elPalNav.querySelectorAll('button').forEach(function (x) { x.classList.remove('on'); });
    b.classList.add('on');
    document.querySelectorAll('.pal').forEach(function (p) { p.hidden = p.dataset.p !== b.dataset.p; });
  });

  /* ── notes ─────────────────────────────────────────────────────── */
  elNotes.addEventListener('input', function () {
    var v = elNotes.value.trim();
    elGenerate.textContent = v ? 'Generate Custom Look' : (S.hasResult ? 'Regenerate' : 'Generate preview');
    if (S.file) _autoGenDebounce(1400);
  });
  elNotes.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (S.file) triggerGenerate(); }
  });

  /* ── zoom ──────────────────────────────────────────────────────── */
  elZoomIn.addEventListener('click',  function () {
    S.zoom = Math.min(S.zoom + .15, 2.5);
    paint2D();
  });
  elZoomOut.addEventListener('click', function () {
    S.zoom = Math.max(S.zoom - .15, .5);
    paint2D();
  });

  /* ── reset ─────────────────────────────────────────────────────── */
  elReset.addEventListener('click', function () {
    S.zoom = 1; S.x = 0; S.y = 0; S.rotX = 0; S.rotY = 0;
    S.colour = 'none'; S.fabric = 'Premium Gabardine';
    S.view = 'front';
    elPalettes.querySelectorAll('button').forEach(function (b) { b.classList.remove('on'); });
    var fp = elPalettes.querySelector('.pal button'); if (fp) fp.classList.add('on');
    elFabrics.querySelectorAll('button').forEach(function (b) { b.classList.remove('on'); });
    var fb = elFabrics.querySelector('button'); if (fb) fb.classList.add('on');
    if (elViews) elViews.querySelectorAll('button').forEach(function (b) {
      var selected = b.dataset.view === S.view;
      b.classList.toggle('on', selected);
      b.setAttribute('aria-pressed', selected ? 'true' : 'false');
    });
    paint2D();
    if (S.file) triggerGenerate();
    else setStatus('Reset.');
  });

  /* ── AI-generated angle controls ───────────────────────────────── */
  var VIEW_ANGLES = ['front', 'left', 'back', 'right'];

  function chooseView(view) {
    if (VIEW_ANGLES.indexOf(view) === -1) return;
    S.view = view;
    elViews.querySelectorAll('button').forEach(function (b) {
      var selected = b.dataset.view === view;
      b.classList.toggle('on', selected);
      b.setAttribute('aria-pressed', selected ? 'true' : 'false');
    });
    if (S.file) triggerGenerate();
    else setStatus('Upload a garment photo to generate the ' + view + ' view.');
  }

  elViews.addEventListener('click', function (e) {
    var b = e.target.closest('button[data-view]');
    if (b) chooseView(b.dataset.view);
  });

  /* ── tool toggle ────────────────────────────────────────────────── */
  elToolMove.addEventListener('click', function () {
    elToolMove.classList.add('on'); elToolColor.classList.remove('on');
    var next = (VIEW_ANGLES.indexOf(S.view) + 1) % VIEW_ANGLES.length;
    chooseView(VIEW_ANGLES[next]);
  });
  elToolColor.addEventListener('click', function () {
    elToolColor.classList.add('on'); elToolMove.classList.remove('on');
    var dock = document.querySelector('.dock');
    if (dock) dock.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    var firstTone = elPalettes.querySelector('.pal:not([hidden]) button');
    if (firstTone) firstTone.focus();
    setStatus('Choose a colour tone to generate a new fitting preview.');
  });

  /* ── WhatsApp contact ───────────────────────────────────────────── */
  elContact.addEventListener('click', function () {
    if (!S.hasResult) return;
    var waBase = document.body.dataset.whatsappUrl || 'https://wa.me/2349166901393';
    var notes  = (elNotes.value || '').trim();
    var msg = 'Hello Omafrans Couture, I would love you to sew this dress for me.\n'
            + 'Size: ' + S.sizeName + ' (' + S.sizeMeasure + ' cm).\n'
            + 'Fabric preference: ' + S.fabric + '.'
            + (notes ? '\nDesign notes: ' + notes : '')
            + '\nI created a fitting preview in your AI Dressing Room.';

    if (!S.generatedUrl) { window.open(waBase + '?text=' + encodeURIComponent(msg), '_blank', 'noopener'); return; }

    fetch(S.generatedUrl).then(function (r) { return r.blob(); }).then(function (blob) {
      var f = new File([blob], 'omafrans-fitting-preview.png', { type: 'image/png' });
      if (navigator.canShare && navigator.canShare({ files: [f] }) && navigator.share) {
        return navigator.share({ files: [f], title: 'Omafrans Couture Fitting Preview', text: msg });
      }
      throw new Error('fallback');
    }).then(function () {
      setStatus('Select WhatsApp in the share menu.', 'ok');
    }).catch(function (err) {
      if (err && err.name === 'AbortError') return;
      if (S.generatedUrl) {
        var a = document.createElement('a');
        a.href = S.generatedUrl; a.download = 'omafrans-fitting-preview.png'; a.click();
      }
      window.open(waBase + '?text=' + encodeURIComponent(msg), '_blank', 'noopener');
      setStatus('Preview downloaded — attach it in the WhatsApp chat.', 'ok');
    });
  });

  /* ── boot ───────────────────────────────────────────────────────── */
  hideLoading();
  paint2D();
  setStatus('Upload a dress photo to begin.');
  loadCollectionDress();
  console.log('[DR] Ready. API:', API_URL);

})();
