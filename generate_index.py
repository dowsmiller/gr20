#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "route_data.json"
OUT_PATH = ROOT / "index.html"


def main() -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    tracks = data.get("tracks", [])
    media = json.loads((ROOT / "media_data.json").read_text(encoding="utf-8")) if (ROOT / "media_data.json").exists() else []

    tracks_json = json.dumps(tracks, separators=(",", ":"))
    media_json = json.dumps(media, separators=(",", ":"))

    total_track_km = round(sum(float(t["distance_km"]) for t in tracks), 1)

    template = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>GR20 Trail Diary</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin="anonymous" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.1/dist/MarkerCluster.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.1/dist/MarkerCluster.Default.css" />
    <style>
      :root {
        --bg-1: #170d11;
        --bg-2: #261a1b;
        --panel: rgba(18, 14, 15, 0.68);
        --panel-strong: rgba(26, 19, 20, 0.82);
        --card: rgba(250, 245, 240, 0.92);
        --dust: #efe5dc;
        --trail: #d44d32;
        --trail-soft: #f7cc9e;
        --forest: #1d4d3d;
        --ink: #f4eee8;
        --muted: rgba(244, 238, 232, 0.74);
        --shadow: rgba(11, 9, 11, 0.46);
      }

      * { box-sizing: border-box; }

      html, body {
        margin: 0;
        width: 100%;
        height: 100%;
        font-family: 'Inter', sans-serif;
        background: radial-gradient(circle at top, rgba(217, 123, 79, 0.28), transparent 28%), linear-gradient(180deg, var(--bg-1), var(--bg-2));
        color: var(--ink);
      }

      body {
        min-height: 100vh;
        overflow: visible;
      }

      #app, #map {
        position: absolute;
        inset: 0;
      }

      #map {
        background: #0f1718;
      }

      #map .leaflet-tile-pane {
        filter: saturate(1.18) contrast(1.12) brightness(0.9);
      }

      #map .leaflet-container {
        background: #1a2b26;
      }

      .leaflet-control-layers,
      .leaflet-control-zoom {
        border: 1px solid rgba(255,255,255,0.12) !important;
        box-shadow: 0 18px 40px rgba(0,0,0,0.35) !important;
        border-radius: 14px !important;
        overflow: hidden;
      }

      .leaflet-control-zoom a,
      .leaflet-control-layers-toggle {
        background: rgba(18, 17, 17, 0.7) !important;
        color: #f6efe8 !important;
      }

      .leaflet-control-layers-toggle {
        background-image: url('https://unpkg.com/leaflet@1.9.4/dist/images/layers.png') !important;
        background-position: center !important;
        background-repeat: no-repeat !important;
      }

      .media-toggle {
        width: 34px;
        height: 34px;
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 6px;
        background: rgba(18, 17, 17, 0.7);
        box-shadow: 0 12px 24px rgba(0,0,0,0.3);
        color: #f6efe8;
        cursor: pointer;
        font-size: 0;
      }

      .media-toggle::before {
        content: '\\1F5BC ';
        font-size: 1rem;
      }

      .map-panel {
        position: absolute;
        z-index: 500;
        top: 16px;
        left: 16px;
        max-width: min(360px, calc(100vw - 32px));
        background: rgba(18, 14, 15, 0.7);
        border: 1px solid rgba(255,255,255,0.12);
        box-shadow: 0 18px 38px rgba(0,0,0,0.34);
        border-radius: 18px;
        padding: 14px 16px 12px;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        pointer-events: none;
      }

      .eyebrow {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 0.68rem;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: #f9d5af;
        font-weight: 800;
      }

      .eyebrow::before {
        content: '';
        width: 9px;
        height: 9px;
        border-radius: 999px;
        background: linear-gradient(180deg, #f7d3a4, #d64a38);
        box-shadow: 0 0 0 3px rgba(214, 74, 56, 0.15);
      }

      h1 {
        margin: 10px 0 0;
        font-size: clamp(1.7rem, 3vw, 2.7rem);
        letter-spacing: -0.065em;
        line-height: 0.96;
        font-weight: 800;
      }

      .stats {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 12px;
      }

      .stat {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 999px;
        padding: 7px 9px;
        font-size: 0.74rem;
        color: var(--muted);
      }

      .stat strong {
        color: var(--ink);
      }

      .media-cluster-icon {
        background: transparent;
        border: 0;
      }

      .media-cluster-preview {
        position: relative;
        width: 76px;
        height: 76px;
        overflow: visible;
        border: 2px solid #fff8f0;
        border-radius: 6px;
        box-shadow: 0 0 0 2px #b92525, 0 12px 24px rgba(0, 0, 0, 0.35);
      }

      .media-cluster-scene {
        width: 100%;
        height: 100%;
        overflow: hidden;
        border-radius: 4px;
      }

      .media-cluster-scene img,
      .media-cluster-scene video {
        display: block;
        width: 100%;
        height: 100%;
        object-fit: cover;
        object-position: center;
      }

      .media-cluster-count {
        position: absolute;
        z-index: 1;
        top: -10px;
        right: -10px;
        display: grid;
        width: 26px;
        height: 26px;
        place-items: center;
        border: 2px solid #fff8f0;
        border-radius: 50%;
        background: #b92525;
        box-shadow: 0 0 0 2px #b92525;
        color: #fff8f0;
        font-size: 0.65rem;
        font-weight: 800;
      }

      .media-preview-icon {
        background: transparent;
        border: 0;
        width: 76px !important;
      }

      .media-preview {
        width: 76px;
        height: 96px;
        overflow: hidden;
        background: rgba(17, 14, 13, 0.94);
        border: 2px solid #fff8f0;
        border-radius: 6px;
        box-shadow: 0 0 0 2px #b92525, 0 12px 24px rgba(0, 0, 0, 0.35);
        cursor: pointer;
        transform-origin: bottom center;
        transition: width 160ms ease, height 160ms ease, transform 160ms ease, box-shadow 160ms ease;
      }

      .media-preview:hover,
      .media-preview.is-expanded {
        width: 210px;
        height: 242px;
        transform: translateY(-4px);
        box-shadow: 0 20px 34px rgba(0, 0, 0, 0.48);
        z-index: 1000;
      }

      .media-preview-scene {
        position: relative;
        width: 100%;
        height: calc(100% - 20px);
        background: #362321;
        overflow: hidden;
      }

      .media-preview-scene img,
      .media-preview-scene video {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        display: block;
        object-fit: cover !important;
        object-position: center;
        pointer-events: none;
      }

      .media-preview-scene .live-preview {
        opacity: 0;
        transition: opacity 160ms ease;
      }

      .media-preview-scene .live-preview.is-ready {
        opacity: 1;
      }

      .media-preview time {
        display: block;
        height: 20px;
        padding: 5px 6px;
        color: #f7efe8;
        font-size: 0.55rem;
        line-height: 14px;
        white-space: nowrap;
      }

      .media-lightbox {
        position: fixed;
        z-index: 2000;
        inset: 0;
        display: none;
        align-items: center;
        justify-content: center;
        padding: 24px;
        background: rgba(8, 7, 7, 0.86);
      }

      .media-lightbox.is-open {
        display: flex;
      }

      .media-lightbox-close {
        position: absolute;
        z-index: 1;
        top: 16px;
        right: 16px;
        width: 40px;
        height: 40px;
        border: 2px solid #fff8f0;
        border-radius: 50%;
        background: #b92525;
        box-shadow: 0 0 0 2px #b92525;
        color: #fff8f0;
        cursor: pointer;
        font-size: 1.5rem;
        line-height: 1;
      }

      .media-lightbox-nav {
        position: absolute;
        z-index: 1;
        top: 50%;
        width: 42px;
        height: 42px;
        border: 2px solid #fff8f0;
        border-radius: 50%;
        background: #b92525;
        box-shadow: 0 0 0 2px #b92525;
        color: #fff8f0;
        cursor: pointer;
        font-size: 1.6rem;
        line-height: 1;
        transform: translateY(-50%);
      }

      .media-lightbox-prev { left: 16px; }
      .media-lightbox-next { right: 16px; }

      .media-toggle {
        width: 38px;
        height: 38px;
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 6px;
        background: rgba(18, 17, 17, 0.78);
        box-shadow: 0 12px 24px rgba(0, 0, 0, 0.32);
        color: #fff8f0;
        cursor: pointer;
        font-size: 1rem;
      }

      .media-lightbox img,
      .media-lightbox > video,
      .media-lightbox-live {
        width: 100%;
        height: 100%;
        border: 3px solid #fff8f0;
        box-shadow: 0 0 0 3px #b92525;
        box-sizing: border-box;
        object-fit: contain;
      }

      .media-lightbox-live {
        position: relative;
      }

      .media-lightbox-live img,
      .media-lightbox-live video {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        border: 0;
        box-shadow: none;
        object-fit: contain;
      }

      .media-lightbox-live video {
        transition: opacity 160ms ease;
      }

      .media-lightbox-live video.is-finished {
        opacity: 0;
      }

      .route-time-tooltip {
        background: rgba(17, 14, 13, 0.94);
        border: 1px solid rgba(255, 248, 240, 0.85);
        border-radius: 4px;
        box-shadow: 0 10px 22px rgba(0, 0, 0, 0.32);
        color: #fff8f0;
        font-size: 0.68rem;
        padding: 4px 6px;
      }

      @media (max-width: 640px) {
        .map-panel {
          top: 12px;
          left: 12px;
          right: 12px;
          max-width: none;
          padding: 12px 14px 10px;
          border-radius: 16px;
        }

        h1 {
          font-size: 1.8rem;
        }
      }
    </style>
  </head>
  <body>
    <div id="app">
      <div id="map" aria-label="Corsica hiking route map"></div>
      <aside class="map-panel" aria-live="polite">
        <div class="eyebrow">GR20 Trail Diary</div>
        <h1>Corsica trail diary</h1>
        <div class="stats">
          <div class="stat"><strong>__STAGE_COUNT__</strong> stages</div>
          <div class="stat"><strong>__TOTAL_KM__ km</strong></div>
        </div>
      </aside>
      <div class="media-lightbox" aria-hidden="true"></div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin="anonymous"></script>
    <script src="https://unpkg.com/leaflet.markercluster@1.5.1/dist/leaflet.markercluster.js"></script>
    <script>
      const tracks = __TRACKS_JSON__;
      const mediaItems = __MEDIA_JSON__;
      let mediaLayer;

      const map = L.map('map', {
        zoomControl: false,
        attributionControl: true,
        preferCanvas: true,
        zoomSnap: 0.5,
        zoomDelta: 0.5,
        wheelPxPerZoomLevel: 40,
        minZoom: 7,
        maxZoom: 17
      });
      L.control.zoom({ position: 'bottomright' }).addTo(map);
      const mediaToggle = L.control({ position: 'bottomleft' });
      mediaToggle.onAdd = function() {
        const button = L.DomUtil.create('button', 'media-toggle');
        button.type = 'button';
        button.title = 'Hide media';
        button.setAttribute('aria-label', 'Hide media');
        L.DomEvent.disableClickPropagation(button);
        button.addEventListener('click', () => {
          const visible = map.hasLayer(mediaLayer);
          if (visible) {
            map.removeLayer(mediaLayer);
            button.title = 'Show media';
            button.setAttribute('aria-label', 'Show media');
          } else {
            map.addLayer(mediaLayer);
            button.title = 'Hide media';
            button.setAttribute('aria-label', 'Hide media');
          }
        });
        return button;
      };

      const terrain = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
        maxZoom: 17,
        attribution: 'Map data: &copy; OpenStreetMap contributors, SRTM | Map style: &copy; OpenTopoMap'
      });

      const hillshade = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Hillshade/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 17,
        opacity: 0.38,
        attribution: 'Tiles &copy; Esri'
      });

      const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 17,
        attribution: 'Tiles &copy; Esri'
      });

      const baseLayers = {
        'Topo relief': L.layerGroup([terrain, hillshade]),
        'Map': L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
          maxZoom: 17,
          attribution: '&copy; OpenStreetMap contributors &copy; CARTO'
        }),
        'Satellite': satellite
      };

      const defaultLayer = baseLayers['Topo relief'];
      defaultLayer.addTo(map);
      L.control.layers(baseLayers, null, { position: 'topright' }).addTo(map);

      function formatTimestamp(ts) {
        const d = new Date(ts);
        return new Intl.DateTimeFormat(undefined, {
          timeZone: 'Europe/Paris',
          day: 'numeric',
          month: 'short',
          hour: '2-digit',
          minute: '2-digit'
        }).format(d);
      }

      function buildFootsteps() {
        const routeLayer = L.layerGroup().addTo(map);
        const allCoords = [];

        tracks.forEach((track) => {
          const coords = track.points.map((point) => [point.lat, point.lon]);
          allCoords.push(...coords);
          const routeLine = L.polyline(coords, {
            color: '#b92525',
            weight: 9,
            opacity: 0.95,
            lineCap: 'round',
            lineJoin: 'round'
          }).addTo(routeLayer);
          L.polyline(coords, {
            color: '#fff8f0',
            weight: 4,
            opacity: 0.98,
            lineCap: 'round',
            lineJoin: 'round',
            interactive: false
          }).addTo(routeLayer);

          routeLine.bindTooltip('', { className: 'route-time-tooltip', sticky: true, direction: 'top', opacity: 1 });
          routeLine.on('mousemove', (event) => {
            let closestPoint = track.points[0];
            let closestDistance = Infinity;
            track.points.forEach((point) => {
              const distance = map.distance(event.latlng, [point.lat, point.lon]);
              if (distance < closestDistance) {
                closestDistance = distance;
                closestPoint = point;
              }
            });
            routeLine.setTooltipContent(formatTimestamp(closestPoint.time));
          });
        });

        const bounds = L.latLngBounds(allCoords);
        map.fitBounds(bounds.pad(0.18), { animate: false });
      }

      buildFootsteps();

      function mediaUrl(fileName) {
        if (!fileName) return '';
        if (fileName.startsWith('photos/')) return fileName;
        const safeName = fileName.split('/').pop();
        return 'photos/' + encodeURI(safeName);
      }

      function mediaPreviewMarkup(item) {
        const imageSrc = item.image ? mediaUrl(item.preview || item.image_path || item.image) : '';
        const expandedImageSrc = item.image ? mediaUrl(item.expanded_preview || item.image_path || item.image) : '';
        const videoSrc = item.video ? mediaUrl(item.preview_video || item.video_path || item.video) : '';
        const media = item.kind === 'live_photo' && videoSrc
          ? '<img src="' + imageSrc + '" data-preview-src="' + imageSrc + '" data-expanded-src="' + expandedImageSrc + '" alt="" /><video class="live-preview" muted playsinline preload="metadata" src="' + videoSrc + '"></video>'
          : imageSrc
            ? '<img src="' + imageSrc + '" data-preview-src="' + imageSrc + '" data-expanded-src="' + expandedImageSrc + '" alt="" />'
            : '<video muted autoplay playsinline loop preload="metadata" src="' + videoSrc + '"></video>';
        return '<div class="media-preview"><div class="media-preview-scene">' + media + '</div><time>' + formatTimestamp(item.time) + '</time></div>';
      }

      function mediaClusterMarkup(item, count) {
        const imageSrc = item.image ? mediaUrl(item.preview || item.image_path || item.image) : '';
        const thumbnail = imageSrc
          ? '<img src="' + imageSrc + '" alt="" />'
          : '<video muted playsinline preload="metadata" src="' + mediaUrl(item.video_path || item.video) + '"></video>';
        return '<div class="media-cluster-preview"><div class="media-cluster-scene">' + thumbnail + '</div><span class="media-cluster-count">+' + (count - 1) + '</span></div>';
      }

      function buildMediaMarkers() {
        if (!mediaItems.length) return;
        mediaLayer = L.markerClusterGroup({
          disableClusteringAtZoom: 16,
          maxClusterRadius: (zoom) => zoom < 11 ? 105 : zoom < 14 ? 76 : 52,
          showCoverageOnHover: false,
          spiderfyOnMaxZoom: true,
          zoomToBoundsOnClick: false,
          iconCreateFunction: function(cluster) {
            const count = cluster.getChildCount();
            const item = cluster.getAllChildMarkers()[0].options.mediaItem;
            return L.divIcon({
              html: mediaClusterMarkup(item, count),
              className: 'media-cluster-icon',
              iconSize: [76, 76],
              iconAnchor: [38, 38]
            });
          }
        }).addTo(map);
        mediaToggle.addTo(map);

        mediaLayer.on('clustermouseover', (event) => {
          const count = event.layer.getChildCount();
          if (count <= 12) event.layer.spiderfy();
        });
        mediaLayer.on('clusterclick', (event) => {
          event.originalEvent.preventDefault();
          openMediaCarousel(event.layer.getAllChildMarkers().map((marker) => marker.options.mediaItem));
        });

        mediaItems.forEach((item) => {
          const marker = L.marker([item.lat, item.lon], {
            icon: L.divIcon({
              className: 'media-marker',
              html: mediaPreviewMarkup(item),
              iconSize: [76, 96],
              iconAnchor: [38, 96]
            }),
            mediaItem: item
          });

          marker.on('click', () => {
            openMediaLightbox(item);
          });
          marker.on('mouseover', () => {
            marker.setZIndexOffset(10000);
            const image = marker.getElement()?.querySelector('img[data-expanded-src]');
            if (image) image.src = image.dataset.expandedSrc;
          });
          marker.on('mouseout', () => {
            marker.setZIndexOffset(0);
            const preview = marker.getElement()?.querySelector('.media-preview');
            const image = preview?.querySelector('img[data-expanded-src]');
            if (image && !preview.classList.contains('is-expanded')) image.src = image.dataset.previewSrc;
          });
          marker.on('add', () => {
            const previewVideo = marker.getElement()?.querySelector('.live-preview');
            if (!previewVideo) return;
            previewVideo.addEventListener('canplay', () => {
              previewVideo.play().then(() => previewVideo.classList.add('is-ready')).catch(() => {});
            }, { once: true });
            previewVideo.addEventListener('ended', () => previewVideo.classList.remove('is-ready'), { once: true });
          });
          mediaLayer.addLayer(marker);
        });
      }

      function openMediaLightbox(item) {
        const lightbox = document.querySelector('.media-lightbox');
        const media = lightboxMediaMarkup(item);
        lightbox.innerHTML = '<button class="media-lightbox-close" type="button" aria-label="Close fullscreen media">&times;</button>' + media;
        activateLightboxLivePhoto(lightbox);
        lightbox.classList.add('is-open');
        lightbox.setAttribute('aria-hidden', 'false');
      }

      function lightboxMediaMarkup(item) {
        const imageSrc = item.image ? mediaUrl(item.image_path || item.image) : '';
        const videoSrc = item.video ? mediaUrl(item.preview_video || item.video_path || item.video) : '';
        if (item.kind === 'live_photo' && imageSrc && videoSrc) {
          return '<div class="media-lightbox-live"><img src="' + imageSrc + '" alt="Trail media" /><video data-live-photo muted autoplay playsinline controls src="' + videoSrc + '"></video></div>';
        }
        return imageSrc
          ? '<img src="' + imageSrc + '" alt="Trail media" />'
          : '<video muted autoplay playsinline loop controls src="' + videoSrc + '"></video>';
      }

      function activateLightboxLivePhoto(lightbox) {
        const video = lightbox.querySelector('video[data-live-photo]');
        if (video) video.addEventListener('ended', () => video.classList.add('is-finished'), { once: true });
      }

      function openMediaCarousel(items) {
        let index = 0;
        const lightbox = document.querySelector('.media-lightbox');
        const showItem = () => {
          const item = items[index];
          const media = lightboxMediaMarkup(item);
          lightbox.innerHTML = '<button class="media-lightbox-close" type="button" aria-label="Close fullscreen media">&times;</button><button class="media-lightbox-nav media-lightbox-prev" type="button" aria-label="Previous media">&#8249;</button>' + media + '<button class="media-lightbox-nav media-lightbox-next" type="button" aria-label="Next media">&#8250;</button>';
          activateLightboxLivePhoto(lightbox);
          lightbox.querySelector('.media-lightbox-prev').addEventListener('click', () => {
            index = (index - 1 + items.length) % items.length;
            showItem();
          });
          lightbox.querySelector('.media-lightbox-next').addEventListener('click', () => {
            index = (index + 1) % items.length;
            showItem();
          });
        };
        showItem();
        lightbox.classList.add('is-open');
        lightbox.setAttribute('aria-hidden', 'false');
      }

      document.querySelector('.media-lightbox').addEventListener('click', (event) => {
        if (event.target === event.currentTarget || event.target.closest('.media-lightbox-close')) {
          event.currentTarget.classList.remove('is-open');
          event.currentTarget.setAttribute('aria-hidden', 'true');
          event.currentTarget.innerHTML = '';
        }
      });

      document.addEventListener('keydown', (event) => {
        const lightbox = document.querySelector('.media-lightbox');
        if (!lightbox.classList.contains('is-open')) return;
        if (event.key === 'ArrowLeft') lightbox.querySelector('.media-lightbox-prev')?.click();
        if (event.key === 'ArrowRight') lightbox.querySelector('.media-lightbox-next')?.click();
        if (event.key === 'Escape') lightbox.querySelector('.media-lightbox-close')?.click();
      });

      buildMediaMarkers();
    </script>
  </body>
</html>
"""

    replacements = {
        '__TRACKS_JSON__': tracks_json,
        '__MEDIA_JSON__': media_json,
        '__STAGE_COUNT__': str(len(tracks)),
        '__TOTAL_KM__': str(total_track_km),
    }

    html = template
    for key, value in replacements.items():
        html = html.replace(key, str(value))

    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Generated HTML: {OUT_PATH}")


if __name__ == "__main__":
    main()
