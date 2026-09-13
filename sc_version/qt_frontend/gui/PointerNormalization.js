.pragma library

function verticalUnit(y, height) {
    if (height <= 0)
        return 0.5
    return Math.max(0.0, Math.min(1.0, y / height))
}
