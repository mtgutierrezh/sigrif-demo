import { Minus, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useMap } from "react-leaflet";

const buttonClass =
  "flex h-11 w-11 items-center justify-center text-bone transition-colors hover:text-surveyor focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-surveyor disabled:cursor-not-allowed disabled:text-iron";

export function ZoomControl() {
  const map = useMap();
  const [zoom, setZoom] = useState(map.getZoom());
  const minZoom = map.getMinZoom();
  const maxZoom = map.getMaxZoom();

  useEffect(() => {
    const update = () => setZoom(map.getZoom());
    map.on("zoomend", update);
    return () => {
      map.off("zoomend", update);
    };
  }, [map]);

  return (
    <div
      className="absolute bottom-28 right-4 z-[1000] flex flex-col overflow-hidden rounded-[3.6px] border border-iron bg-obsidian/90 backdrop-blur-sm md:right-[400px]"
      role="group"
      aria-label="Controles de zoom"
    >
      <button
        type="button"
        className={buttonClass}
        onClick={() => map.zoomIn()}
        disabled={zoom >= maxZoom}
        aria-label="Acercar"
      >
        <Plus size={18} strokeWidth={1.5} aria-hidden />
      </button>
      <button
        type="button"
        className={`${buttonClass} border-t border-iron`}
        onClick={() => map.zoomOut()}
        disabled={zoom <= minZoom}
        aria-label="Alejar"
      >
        <Minus size={18} strokeWidth={1.5} aria-hidden />
      </button>
    </div>
  );
}
