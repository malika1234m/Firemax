export function formatHazardLabel(hazardType) {
  if (hazardType === 'camera_offline') return 'Camera Offline'
  const spaced = hazardType.replace(/_/g, ' ')
  const capitalized = spaced.charAt(0).toUpperCase() + spaced.slice(1)
  return `${capitalized} Detected`
}
