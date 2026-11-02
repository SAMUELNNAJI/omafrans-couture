/**
 * dressing-room.js  — Omafrans Couture AI Dressing Room
 * Requires Three.js loaded before this script.
 */
(function () {
  'use strict';

  /* ── guard ─────────────────────────────────────────────────────── */
  if (!document.getElementById('roomFile')) return;

  /* ── resolve the API endpoint ──────────────────────────────────── */
  var API_URL = (window.DR_GENERATE_URL || '/api/dressing-room/generate/');
  console.log('[DR] API endpoint:', API_URL);

  /* ── element refs ───────────────────────────────────────────────── */
  var elFile        = document.getElementById('roomFile');
  var elThumb       = document.getElementById('roomThumb');
  var elDress2D     = document.getElementById('roomDress');
  var elFigure      = document.getElementById('figure');
  var elFitBox      = document.getElementById('fitBox');
  var elCanvas      = document.getElementById('canvas');
  var elThreeMount  = document.getElementById('threeMount');
  var elGenerated   = document.getElementById('generatedPreview') || document.getElementById('roomGenerated');
  var elDragHint    = document.getElementById('roomDragHint') || document.querySelector('.room-drag-hint');
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

  /* ── state ───────────────────────────────────────────────────────  */
  var S = {
    file:         null,
    sourceUrl:    '',
    generatedUrl: '',
    sizeName:     'M',
    sizeMeasure:  'Bust 90 · Waist 72 · Hips 96',
    fabric:       'Premium Gabardine',
    colour:       'none',
    colourCSS:    '',
    zoom:         1, x: 0, y: 0, rotY: 0, rotX: 0,
    hasResult:    false,
    busy:         false,
  };

  var SIZE_SCALE = { XS:.84, S:.92, M:1, L:1.08, XL:1.17, '2XL':1.27 };

  /* ── helpers ─────────────────────────────────────────────────────── */
  function setStatus(msg, type) {
    elStatus.textContent = msg;
    elStatus.className = 'room-status' + (type ? ' room-status--' + type : '');
  }

  function showLoading(msg) {
    if (elOverlayText) elOverlayText.textContent = msg || 'Generating your fitting preview…';
    if (elOverlay) {
      elOverlay.hidden = false;
      elOverlay.style.display = 'flex';
    }
  }

  function hideLoading() {
    if (elOverlay) {
      elOverlay.hidden = true;
      elOverlay.style.display = 'none';
    }
  }

  function paint2D() {
    var sc = SIZE_SCALE[S.sizeName] || 1;
    elFitBox.style.transform = 'scaleX(' + sc + ')';
    elDress2D.style.filter   = S.colourCSS || '';
    elFigure.style.transform = 'translate(' + S.x + 'px,' + S.y + 'px) scale(' + S.zoom + ') rotateY(' + S.rotY + 'deg) rotateX(' + S.rotX + 'deg)';
  }

  function showResult2D() {
    if (elGenerated) {
      elGenerated.src = S.generatedUrl;
      elGenerated.hidden = false;
      elGenerated.style.display = 'block';
    } else {
      elDress2D.src = S.generatedUrl;
      elDress2D.hidden = false;
    }
    if (elThreeMount) {
      elThreeMount.hidden = true;
      elThreeMount.style.display = 'none';
    }
    if (elFigure) {
      elFigure.hidden = true;
      elFigure.style.display = 'none';
    }
    if (elDragHint) {
      elDragHint.hidden = true;
      elDragHint.style.display = 'none';
    }
    elCanvas.classList.remove('mode-3d');
  }

  function showResult3D() {
    if (elGenerated) {
      elGenerated.hidden = true;
      elGenerated.style.display = 'none';
    }
    if (elFigure) {
      elFigure.hidden = true;
      elFigure.style.display = 'none';
    }
    if (elThreeMount) {
      elThreeMount.hidden = false;
      elThreeMount.style.display = 'block';
    }
    if (elDragHint) {
      elDragHint.hidden = false;
      elDragHint.style.display = 'flex';
    }
    elCanvas.classList.add('mode-3d');
  }

  /* ── Three.js ────────────────────────────────────────────────────── */
  var T3 = null;

  function initThree() {
    if (!window.THREE || !elThreeMount || T3) return;
    try {
      elThreeMount.hidden = false;
      elThreeMount.style.display = 'block';
      var W = elThreeMount.clientWidth  || 640;
      var H = elThreeMount.clientHeight || 500;
      var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setSize(W, H);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setClearColor(0x000000, 0);
      elThreeMount.innerHTML = '';
      elThreeMount.appendChild(renderer.domElement);

      var scene  = new THREE.Scene();
      var camera = new THREE.PerspectiveCamera(38, W / H, 0.1, 100);
      camera.position.z = 2.8;

      var key = new THREE.DirectionalLight(0xfff4e0, 1.8);
      key.position.set(-1.5, 2.5, 2); scene.add(key);
      var fill = new THREE.DirectionalLight(0xb4caff, 0.7);
      fill.position.set(2, 0.5, 1); scene.add(fill);
      scene.add(new THREE.AmbientLight(0xffffff, 0.5));

      var bg = new THREE.Mesh(
        new THREE.PlaneGeometry(8, 8),
        new THREE.MeshBasicMaterial({ color: 0x120a1e })
      );
      bg.position.z = -1.5;
      scene.add(bg);

      var mat  = new THREE.MeshStandardMaterial({ color: 0xffffff, side: THREE.DoubleSide, transparent: true });
      var mesh = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 2.13), mat);
      scene.add(mesh);

      T3 = { renderer: renderer, scene: scene, camera: camera, mesh: mesh, mat: mat };

      (function loop() {
        T3.raf = requestAnimationFrame(loop);
        renderer.render(scene, camera);
      })();

      if (window.ResizeObserver) {
        new ResizeObserver(function () {
          var w = elThreeMount.clientWidth, h = elThreeMount.clientHeight;
          if (!w || !h) return;
          renderer.setSize(w, h);
          camera.aspect = w / h;
          camera.updateProjectionMatrix();
        }).observe(elThreeMount);
      }
      console.log('[DR] Three.js initialised');
    } catch (e) {
      console.error('[DR] Three.js init failed:', e);
      T3 = null;
    }
  }

  function applyRot() {
    if (!T3) return;
    T3.mesh.rotation.y = S.rotY * Math.PI / 180;
    T3.mesh.rotation.x = S.rotX * Math.PI / 180;
  }

  function loadTex(dataUrl, callback) {
    if (!T3) {
      if (callback) callback(false);
      return;
    }
    new THREE.TextureLoader().load(
      dataUrl,
      function (tex) {
        if (THREE.SRGBColorSpace !== undefined) {
          tex.colorSpace = THREE.SRGBColorSpace;
        } else if (THREE.sRGBEncoding !== undefined) {
          tex.encoding = THREE.sRGBEncoding;
        }
        T3.mat.map = tex;
        T3.mat.needsUpdate = true;
        applyRot();
        console.log('[DR] 3D texture loaded');
        if (callback) callback(true);
      },
      undefined,
      function (err) {
        console.warn('[DR] 3D texture load failed:', err);
        if (callback) callback(false);
      }
    );
  }

  /* ── file load ───────────────────────────────────────────────────── */
  function loadFile(file) {
    if (!file) return;
    if (!file.type.startsWith('image/')) { setStatus('Please choose an image file.', 'warn'); return; }
    if (file.size > 12 * 1024 * 1024)   { setStatus('Image too large (max 12 MB).', 'warn'); return; }

    if (S.sourceUrl)    URL.revokeObjectURL(S.sourceUrl);
    if (S.generatedUrl) URL.revokeObjectURL(S.generatedUrl);
    S.file = file;
    S.sourceUrl = URL.createObjectURL(file);
    S.generatedUrl = '';
    S.hasResult = false;

    elDress2D.src = S.sourceUrl;
    elDress2D.hidden = false;
    elThumb.src = S.sourceUrl;
    elFigure.hidden = false;
    elFigure.style.display = '';
    if (elGenerated) {
      elGenerated.hidden = true;
      elGenerated.style.display = 'none';
    }
    if (elThreeMount) {
      elThreeMount.hidden = true;
      elThreeMount.style.display = 'none';
    }
    if (elDragHint) {
      elDragHint.hidden = true;
      elDragHint.style.display = 'none';
    }
    elCanvas.classList.remove('mode-3d');

    elContact.disabled     = true;
    elGenerate.disabled    = false;
    elGenerate.textContent = 'Generate preview';
    S.x = S.y = S.rotX = S.rotY = 0;
    paint2D();
    setStatus('Dress loaded. Click "Generate preview".');
    console.log('[DR] File loaded:', file.name, file.size);
  }

  elFile.addEventListener('change', function (e) { loadFile(e.target.files[0]); });

  function loadCollectionDress() {
    var imageUrl = document.body.dataset.tryOnImage;
    if (!imageUrl) return;

    var dressName = document.body.dataset.tryOnName || 'selected collection dress';
    setStatus('Loading ' + dressName + '…');
    fetch(imageUrl)
      .then(function (response) {
        if (!response.ok) throw new Error('Image request failed (' + response.status + ').');
        return response.blob();
      })
      .then(function (blob) {
        var imageType = blob.type.indexOf('image/') === 0 ? blob.type : 'image/png';
        var extension = imageType === 'image/jpeg' ? 'jpg'
          : imageType === 'image/webp' ? 'webp' : 'png';
        var file = new File([blob], 'collection-dress.' + extension, { type: imageType });
        loadFile(file);
        elGenerate.click();
      })
      .catch(function (error) {
        setStatus('Could not load this collection dress. Please upload an image and try again.', 'error');
        console.error('[DR] Collection dress load failed:', error);
      });
  }

  /* ── GENERATE ────────────────────────────────────────────────────── */
  elGenerate.addEventListener('click', function () {
    console.log('[DR] Generate clicked. file:', S.file ? S.file.name : 'NONE', 'busy:', S.busy);

    if (!S.file) {
      setStatus('Upload a dress photo first.', 'warn');
      elFile.focus();
      return;
    }
    if (S.busy) { console.log('[DR] Already busy, ignoring click'); return; }

    S.busy = true;
    elGenerate.disabled    = true;
    elGenerate.textContent = 'Generating…';
    elContact.disabled     = true;
    showLoading('Our AI is fitting the dress…');
    setStatus('');

    var fd = new FormData();
    fd.append('dress',   S.file);
    fd.append('size',    S.sizeName);
    fd.append('fabric',  S.fabric);
    fd.append('colour',  S.colour);
    fd.append('notes',   (elNotes.value || '').trim().slice(0, 240));

    console.log('[DR] Posting to', API_URL, '— size:', S.sizeName, 'fabric:', S.fabric);

    // Keep the browser request open for Gemini's image-generation latency.
    var ctrl    = new AbortController();
    var timerID = setTimeout(function () {
      ctrl.abort();
      console.error('[DR] Request timed out after 110 s');
    }, 110000);

    fetch(API_URL, { method: 'POST', body: fd, signal: ctrl.signal })
      .then(function (res) {
        console.log('[DR] Response status:', res.status, res.statusText);
        return res.text().then(function (txt) {
          return { status: res.status, text: txt };
        });
      })
      .then(function (obj) {
        clearTimeout(timerID);
        console.log('[DR] Raw response (first 120 chars):', obj.text.slice(0, 120));

        var data;
        try { data = JSON.parse(obj.text); }
        catch (_) { throw new Error('Non-JSON response (' + obj.status + '): ' + obj.text.slice(0, 80)); }

        if (obj.status !== 200 || data.error) {
          throw new Error(data.error || 'Server error ' + obj.status);
        }

        /* --- decode base64 PNG --- */
        var b64    = data.image;
        var binary = atob(b64);
        var arr    = new Uint8Array(binary.length);
        for (var i = 0; i < binary.length; i++) arr[i] = binary.charCodeAt(i);
        var blob   = new Blob([arr], { type: 'image/png' });

        if (S.generatedUrl) URL.revokeObjectURL(S.generatedUrl);
        S.generatedUrl = URL.createObjectURL(blob);
        S.hasResult    = true;
        S.busy         = false;

        console.log('[DR] Image decoded. Blob size:', blob.size, 'bytes. Showing preview...');

        /* --- display result in 3D or fallback 2D --- */
        var readyMsg = data.is_ai
          ? 'AI fitting generated with Gemini — drag to rotate. Add notes and regenerate anytime.'
          : 'No AI image was returned. Please try again.';

        initThree();
        if (T3) {
          showResult3D();
          loadTex(S.generatedUrl, function (success) {
            if (!success) {
              console.warn('[DR] 3D texture failed, falling back to 2D view');
              showResult2D();
            }
            hideLoading();
            elContact.disabled     = false;
            elGenerate.disabled    = false;
            elGenerate.textContent = 'Regenerate';
            setStatus(readyMsg, 'ok');
          });
        } else {
          showResult2D();
          hideLoading();
          elContact.disabled     = false;
          elGenerate.disabled    = false;
          elGenerate.textContent = 'Regenerate';
          setStatus(readyMsg, 'ok');
        }

        // Safety fallback: ensure loading overlay never stays stuck
        setTimeout(function () {
          hideLoading();
          if (elGenerate) elGenerate.disabled = false;
        }, 1200);
      })
      .catch(function (err) {
        clearTimeout(timerID);
        S.busy = false;
        hideLoading();
        elGenerate.disabled    = false;
        elGenerate.textContent = 'Try again';

        var msg = err.name === 'AbortError'
          ? 'Request timed out. Check your connection and try again.'
          : 'Error: ' + err.message;

        setStatus(msg, 'error');
        console.error('[DR] Generate failed:', err);
      });
  });

  /* ── settings change ─────────────────────────────────────────────── */
  function markStale() {
    if (S.hasResult) {
      elGenerate.textContent = 'Regenerate';
      setStatus('Setting changed — click "Regenerate" to update.');
    }
  }

  elNotes.addEventListener('input', markStale);

  elSizeButtons.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    elSizeButtons.querySelectorAll('button').forEach(function (x) { x.classList.remove('on'); });
    b.classList.add('on');
    S.sizeName    = b.textContent.trim();
    S.sizeMeasure = b.dataset.m || '';
    elSizeInfo.textContent = 'Size ' + S.sizeName + ' · ' + S.sizeMeasure + ' cm';
    paint2D(); markStale();
  });

  elFabrics.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    elFabrics.querySelectorAll('button').forEach(function (x) { x.classList.remove('on'); });
    b.classList.add('on');
    S.fabric = b.textContent.trim();
    paint2D(); markStale();
  });

  elPalettes.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    elPalettes.querySelectorAll('button').forEach(function (x) { x.classList.remove('on'); });
    b.classList.add('on');
    S.colour    = b.dataset.f || 'none';
    S.colourCSS = b.dataset.f || '';
    paint2D(); markStale();
  });

  elPalNav.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    elPalNav.querySelectorAll('button').forEach(function (x) { x.classList.remove('on'); });
    b.classList.add('on');
    document.querySelectorAll('.pal').forEach(function (p) { p.hidden = p.dataset.p !== b.dataset.p; });
  });

  /* ── zoom ─────────────────────────────────────────────────────────── */
  elZoomIn.addEventListener('click',  function () { S.zoom = Math.min(S.zoom + .15, 2.5); paint2D(); if (T3) T3.camera.position.z = Math.max(1.2, 2.8 - (S.zoom-1)*.8); });
  elZoomOut.addEventListener('click', function () { S.zoom = Math.max(S.zoom - .15, .5);  paint2D(); if (T3) T3.camera.position.z = Math.max(1.2, 2.8 - (S.zoom-1)*.8); });

  /* ── reset ───────────────────────────────────────────────────────── */
  elReset.addEventListener('click', function () {
    S.zoom = 1; S.x = 0; S.y = 0; S.rotX = 0; S.rotY = 0;
    S.colour = 'none'; S.colourCSS = ''; S.fabric = 'Premium Gabardine';
    elPalettes.querySelectorAll('button').forEach(function (b) { b.classList.remove('on'); });
    var fp = elPalettes.querySelector('.pal button'); if (fp) fp.classList.add('on');
    elFabrics.querySelectorAll('button').forEach(function (b) { b.classList.remove('on'); });
    var fb = elFabrics.querySelector('button'); if (fb) fb.classList.add('on');
    if (T3) { T3.mesh.rotation.set(0,0,0); T3.camera.position.z = 2.8; }
    paint2D();
  });

  /* ── drag / rotate ───────────────────────────────────────────────── */
  var drag = null;

  elCanvas.addEventListener('pointerdown', function (e) {
    if (e.target.closest('button') || e.target.closest('label')) return;
    drag = { sx: e.clientX, sy: e.clientY, rotY: S.rotY, rotX: S.rotX, px: S.x, py: S.y,
             is3d: elCanvas.classList.contains('mode-3d') };
    elCanvas.setPointerCapture(e.pointerId);
    elCanvas.classList.add('grab');
  });

  elCanvas.addEventListener('pointermove', function (e) {
    if (!drag) return;
    var dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
    if (drag.is3d) {
      S.rotY = Math.max(-75, Math.min(75, drag.rotY + dx * .45));
      S.rotX = Math.max(-15, Math.min(15, drag.rotX - dy * .12));
      applyRot();
    } else {
      S.x = drag.px + dx; S.y = drag.py + dy; paint2D();
    }
  });

  ['pointerup','pointercancel','lostpointercapture'].forEach(function (ev) {
    elCanvas.addEventListener(ev, function () { drag = null; elCanvas.classList.remove('grab'); });
  });

  /* ── tool toggle ─────────────────────────────────────────────────── */
  elToolMove.addEventListener('click', function () { elToolMove.classList.add('on'); elToolColor.classList.remove('on'); });
  elToolColor.addEventListener('click', function () {
    elToolColor.classList.add('on'); elToolMove.classList.remove('on');
    var dock = document.querySelector('.dock');
    if (dock) dock.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });

  /* ── WhatsApp contact ────────────────────────────────────────────── */
  elContact.addEventListener('click', function () {
    if (!S.hasResult) return;
    var waBase = document.body.dataset.whatsappUrl || 'https://wa.me/2349166901393';
    var notes  = (elNotes.value || '').trim();
    var msg = 'Hello Omafrans Couture, I would love you to sew this dress for me.\n'
            + 'Size: ' + S.sizeName + ' (' + S.sizeMeasure + ' cm).\n'
            + 'Fabric: ' + S.fabric + '.'
            + (notes ? '\nDesign notes: ' + notes : '')
            + '\nI created a fitting preview in your AI Dressing Room.';

    if (S.generatedUrl) {
      fetch(S.generatedUrl)
        .then(function (r) { return r.blob(); })
        .then(function (blob) {
          var imgFile = new File([blob], 'omafrans-fitting-preview.png', { type: 'image/png' });
          if (navigator.canShare && navigator.canShare({ files: [imgFile] }) && navigator.share) {
            return navigator.share({ files: [imgFile], title: 'Omafrans Couture Fitting Preview', text: msg });
          }
          throw new Error('no-share');
        })
        .then(function () {
          setStatus('Select WhatsApp in the share menu.', 'ok');
        })
        .catch(function (err) {
          if (err && err.name === 'AbortError') return;
          // Fallback: download + open WA
          var a = document.createElement('a');
          a.href = S.generatedUrl; a.download = 'omafrans-fitting-preview.png'; a.click();
          window.open(waBase + '?text=' + encodeURIComponent(msg), '_blank', 'noopener');
          setStatus('Preview downloaded. Attach it in the WhatsApp chat.', 'ok');
        });
    } else {
      window.open(waBase + '?text=' + encodeURIComponent(msg), '_blank', 'noopener');
    }
  });

  /* ── boot ────────────────────────────────────────────────────────── */
  hideLoading();
  paint2D();
  setStatus('Upload a dress photo to begin.');
  loadCollectionDress();
  console.log('[DR] Dressing room ready. API:', API_URL);

})();
