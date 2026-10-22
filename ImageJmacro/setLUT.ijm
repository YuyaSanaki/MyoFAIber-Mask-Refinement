// Keep these RGB bytes in sync with CLASS_RGB in refine_masks.py.
// Initialize arrays
r = newArray(256);
g = newArray(256);
b = newArray(256);

// Reset all to Black first
for (i=0; i<256; i++) {
    r[i]=0; g[i]=0; b[i]=0;
}

// --- Soft Immunostaining Colors (v3) ---

// Label 0: Soft Cyan - Uncertain (Muted Teal)
r[0] = 100; g[0] = 200; b[0] = 210; 

// Label 1: Light Gray - Background
r[1] = 230; g[1] = 230; b[1] = 230;

// Label 2: Soft Magenta - TypeIIB (Orchid)
r[2] = 210; g[2] = 130; b[2] = 210;

// Label 3: Soft Green - TypeI (Sage)
r[3] = 130; g[3] = 190; b[3] = 130;

// Label 4: Steel Blue - Membrane
r[4] = 70;  g[4] = 130; b[4] = 180;

// Label 5: Soft Red - TypeIIA (Salmon/Coral)
r[5] = 230; g[5] = 115; b[5] = 115;

// Label 6: Soft Black - TypeIIX (Charcoal)
r[6] = 50;  g[6] = 50;  b[6] = 50;

// Label 7: Soft Gold - Vessel (Ochre)
r[7] = 220; g[7] = 190; b[7] = 80;

// Label 8: Soft Indigo - Nuclei (DAPI-like)
// Distinct from Membrane (Steel Blue)
r[8] = 90;  g[8] = 90;  b[8] = 210;

// Apply and Update
setLut(r, g, b);
setMinAndMax(0, 255); 
updateDisplay();