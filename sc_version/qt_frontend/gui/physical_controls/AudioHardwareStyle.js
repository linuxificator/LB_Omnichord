.pragma library

function family(id) {
    switch (Number(id)) {
    case 1:
        return {
            panel: "#c8c8c4",
            bezel: "#777772",
            capTop: "#60605c",
            capMid: "#60605c",
            capBottom: "#60605c",
            highlight: "transparent",
            index: "#f2d56b",
            slot: "#080909",
            metalTop: "#b6b9b4",
            metalMid: "#b6b9b4",
            metalBottom: "#b6b9b4",
            accent: "#d8d8d2"
        }
    case 6:
        return {
            panel: "#d5d0c2",
            bezel: "#6b675e",
            capTop: "#57595a",
            capMid: "#353638",
            capBottom: "#171819",
            highlight: "#bdb8aa",
            index: "#efe6ce",
            slot: "#0b0c0c",
            metalTop: "#eff1ed",
            metalMid: "#b7bbb7",
            metalBottom: "#777b77",
            accent: "#d9d9d5"
        }
    default:
        return {
            panel: "#c8c8c4",
            bezel: "#7a7a75",
            capTop: "#81817c",
            capMid: "#60605c",
            capBottom: "#343432",
            highlight: "#bab8ae",
            index: "#f2d56b",
            slot: "#080909",
            metalTop: "#eceeea",
            metalMid: "#b6b9b4",
            metalBottom: "#777b76",
            accent: "#d8d8d2"
        }
    }
}
