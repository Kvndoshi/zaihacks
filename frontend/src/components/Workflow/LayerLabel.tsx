export function LayerLabel({ layer }: { layer: number }) {
  return (
    <div className="text-xs font-semibold text-friction-muted uppercase tracking-wider">
      Layer {layer}
    </div>
  );
}
