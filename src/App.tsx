import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

const esriImageryStyle = {
  version: 8,
  sources: {
    esri: {
      type: "raster",
      tiles: [
        "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      attribution:
        "© Esri, Maxar, Earthstar Geographics, CNES/Airbus DS, USDA, USGS, AeroGRID, IGN",
    },
  },
  layers: [{ id: "esri-world-imagery", type: "raster", source: "esri" }],
};

type AOI = {
  id: string;
  name?: string;
  bbox?: [number, number, number, number]; // [minLon, minLat, maxLon, maxLat]
};

function bboxToPolygon(b: [number, number, number, number]) {
  const [minLon, minLat, maxLon, maxLat] = b;
  return [
    [
      [minLon, minLat],
      [maxLon, minLat],
      [maxLon, maxLat],
      [minLon, maxLat],
      [minLon, minLat],
    ],
  ];
}

export default function App() {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  const resetTimerRef = useRef<number | null>(null);

  const [emailSending, setEmailSending] = useState(false);
  const [emailButtonText, setEmailButtonText] = useState("Send email report");
  const [emailStatus, setEmailStatus] = useState("");

  useEffect(() => {
    // backend health check
    fetch("/api/health")
      .then((r) => r.json())
      .then((data) => console.log("Backend health:", data))
      .catch((err) => console.error("Backend health error:", err));

    if (!mapContainer.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: esriImageryStyle as any,
      center: [-25.7, 37.8],
      zoom: 6,
    });

    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl(), "top-right");

    const loadAOIs = async () => {
      try {
        const res = await fetch("/aois");
        if (!res.ok) {
          const txt = await res.text();
          throw new Error(
            `AOIs fetch failed: ${res.status} ${res.statusText} | ${txt}`
          );
        }

        const aois: AOI[] = await res.json();
        if (!aois.length) return;

        const validAoIs = aois.filter(
          (a) => a.bbox && a.bbox.length === 4
        ) as Required<AOI>[];

        if (!validAoIs.length) {
          console.warn("No valid AOIs with bbox returned.");
          return;
        }

        // polygons
        const polyFeatures = validAoIs.map((a) => ({
          type: "Feature",
          properties: { id: a.id, name: a.name ?? a.id },
          geometry: { type: "Polygon", coordinates: bboxToPolygon(a.bbox) },
        }));

        // points (bbox center)
        const pointFeatures = validAoIs.map((a) => {
          const [minLon, minLat, maxLon, maxLat] = a.bbox;
          const center: [number, number] = [
            (minLon + maxLon) / 2,
            (minLat + maxLat) / 2,
          ];

          return {
            type: "Feature",
            properties: { id: a.id, name: a.name ?? a.id },
            geometry: { type: "Point", coordinates: center },
          };
        });

        const polys = {
          type: "FeatureCollection",
          features: polyFeatures,
        } as any;

        const points = {
          type: "FeatureCollection",
          features: pointFeatures,
        } as any;

        // --- POLYGONS source+layers ---
        if (!map.getSource("aoi-polys")) {
          map.addSource("aoi-polys", { type: "geojson", data: polys });

          map.addLayer({
            id: "aoi-polys-fill",
            type: "fill",
            source: "aoi-polys",
            paint: {
              "fill-opacity": 0.15,
              "fill-color": "#00a2ff",
            },
          });

          map.addLayer({
            id: "aoi-polys-outline",
            type: "line",
            source: "aoi-polys",
            paint: {
              "line-width": 2,
              "line-color": "#00a2ff",
            },
          });
        } else {
          (map.getSource("aoi-polys") as maplibregl.GeoJSONSource).setData(
            polys
          );
        }

        // --- POINTS source+layers (circle always + label from certain zoom) ---
        if (!map.getSource("aoi-points")) {
          map.addSource("aoi-points", { type: "geojson", data: points });

          // circles (always visible)
          map.addLayer({
            id: "aoi-points-layer",
            type: "circle",
            source: "aoi-points",
            paint: {
              "circle-radius": 4,
              "circle-color": "#ba202a",
              "circle-stroke-width": 2,
              "circle-stroke-color": "#000000",
            },
          });

          // labels (only visible from minzoom)
          map.addLayer({
            id: "aoi-labels",
            type: "symbol",
            source: "aoi-points",
            minzoom: 6,
            layout: {
              "text-field": ["get", "name"],
              "text-size": 14,
              "text-offset": [0, 1.2],
              "text-anchor": "top",
              "text-allow-overlap": false,
              "text-ignore-placement": false,
            },
            paint: {
              "text-color": "#111827",
              "text-halo-color": "#ffffff",
              "text-halo-width": 2,
            },
          });
        } else {
          (map.getSource("aoi-points") as maplibregl.GeoJSONSource).setData(
            points
          );

          // ak by náhodou layer neexistoval (napr. hot-reload), doplň ho
          if (!map.getLayer("aoi-points-layer")) {
            map.addLayer({
              id: "aoi-points-layer",
              type: "circle",
              source: "aoi-points",
              paint: {
                "circle-radius": 4,
                "circle-color": "#ba202a",
                "circle-stroke-width": 2,
                "circle-stroke-color": "#000000",
              },
            });
          }

          if (!map.getLayer("aoi-labels")) {
            map.addLayer({
              id: "aoi-labels",
              type: "symbol",
              source: "aoi-points",
              minzoom: 10,
              layout: {
                "text-field": ["get", "name"],
                "text-size": 12,
                "text-offset": [0, 1.2],
                "text-anchor": "top",
                "text-allow-overlap": false,
                "text-ignore-placement": false,
              },
              paint: {
                "text-color": "#111827",
                "text-halo-color": "#ffffff",
                "text-halo-width": 2,
              },
            });
          }
        }

        // fit bounds
        const bounds = new maplibregl.LngLatBounds();
        validAoIs.forEach((a) => {
          const [minLon, minLat, maxLon, maxLat] = a.bbox;
          bounds.extend([minLon, minLat]);
          bounds.extend([maxLon, maxLat]);
        });

        if (!bounds.isEmpty()) {
          map.fitBounds(bounds, { padding: 80, duration: 0 });
        }

        map.resize();
      } catch (err) {
        console.error("Failed to load AOIs:", err);
      }
    };

    map.on("load", loadAOIs);

    return () => {
      map.off("load", loadAOIs);
      map.remove();
      mapRef.current = null;

      if (resetTimerRef.current) {
        window.clearTimeout(resetTimerRef.current);
        resetTimerRef.current = null;
      }
    };
  }, []);

  async function sendEmailReport() {
    try {
      // ak už beží timeout z minulého odoslania, zruš ho
      if (resetTimerRef.current) {
        window.clearTimeout(resetTimerRef.current);
        resetTimerRef.current = null;
      }

      setEmailSending(true);
      setEmailButtonText("Sending...");
      setEmailStatus("");

      const res = await fetch("/api/email-latest-fc-all", { method: "GET" });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`HTTP ${res.status}: ${txt}`);
      }

      // len prečítaj odpoveď (neukazuj queued_email/count)
      await res.json();

      setEmailStatus("✅ Email report sent!");
      setEmailButtonText("Sent");

      // po 5 sekundách vráť späť na default
      resetTimerRef.current = window.setTimeout(() => {
        setEmailStatus("");
        setEmailButtonText("Send email report");
        resetTimerRef.current = null;
      }, 5000);
    } catch (e: any) {
      setEmailStatus(`❌ ${e.message}`);
      setEmailButtonText("Send email report");
    } finally {
      setEmailSending(false);
    }
  }

  // farby tlačidla podľa stavu
  const buttonBg =
    emailButtonText === "Sent"
      ? "#58d68c"
      : emailSending
      ? "#a6242f"
      : "#000000";

  return (
    <div style={{ height: "100vh", width: "100vw", position: "relative" }}>
      <div ref={mapContainer} style={{ height: "100%", width: "100%" }} />

      <div
        style={{
          position: "absolute",
          top: 12,
          left: 12,
          background: "white",
          padding: 12,
          borderRadius: 8,
          boxShadow: "0 2px 10px rgba(0,0,0,0.15)",
          minWidth: 240,
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <button
          onClick={sendEmailReport}
          disabled={emailSending || emailButtonText === "Sent"}
          style={{
            width: "100%",
            padding: "12px 16px",
            cursor: emailSending ? "not-allowed" : "pointer",
            fontWeight: 700,
            opacity: emailSending ? 0.85 : 1,
            backgroundColor: buttonBg,
            color: "white",
            border: "none",
            borderRadius: 10,
            outline: "none",
            boxShadow: "none",
          }}
        >
          {emailButtonText}
        </button>

        {emailStatus && (
          <div style={{ marginTop: 10, fontSize: 13, color: "#111827" }}>
            {emailStatus}
          </div>
        )}
      </div>
    </div>
  );
}
