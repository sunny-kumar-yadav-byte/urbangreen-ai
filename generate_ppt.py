import sys
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

def create_deck(output_path="UrbanGreen_AI_Presentation.pptx"):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Color Palette: Urban Environmental & Sustainable Theme
    DARK_BG = RGBColor(15, 32, 23)       # Deep Forest Night
    WHITE = RGBColor(255, 255, 255)
    OFF_WHITE = RGBColor(245, 247, 245)
    EMERALD = RGBColor(46, 204, 113)     # Vibrant Green
    FOREST = RGBColor(23, 107, 69)       # Medium Forest Green
    LIGHT_GREEN = RGBColor(230, 245, 235)
    CARD_BG = RGBColor(255, 255, 255)
    TEXT_DARK = RGBColor(26, 38, 30)
    TEXT_MUTED = RGBColor(100, 115, 105)
    ACCENT_ORANGE = RGBColor(230, 126, 34)
    BORDER_COLOR = RGBColor(210, 225, 215)

    def add_header(slide, title_text, category_text="URBANGREEN AI | IEEE HACKATHON 2026"):
        # Category label
        tb_cat = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.4))
        tf_cat = tb_cat.text_frame
        tf_cat.word_wrap = True
        p_cat = tf_cat.paragraphs[0]
        p_cat.text = category_text.upper()
        p_cat.font.name = "Calibri"
        p_cat.font.size = Pt(11)
        p_cat.font.bold = True
        p_cat.font.color.rgb = FOREST

        # Main Title
        tb_title = slide.shapes.add_textbox(Inches(0.8), Inches(0.7), Inches(11.7), Inches(0.8))
        tf_title = tb_title.text_frame
        tf_title.word_wrap = True
        p_title = tf_title.paragraphs[0]
        p_title.text = title_text
        p_title.font.name = "Calibri"
        p_title.font.size = Pt(26)
        p_title.font.bold = True
        p_title.font.color.rgb = TEXT_DARK

    def set_slide_background(slide, color):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = color
        bg.line.fill.background()
        return bg

    def add_card(slide, left, top, width, height, bg_color=CARD_BG, border_color=BORDER_COLOR):
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = bg_color
        if border_color:
            shape.line.color.rgb = border_color
            shape.line.width = Pt(1.5)
        else:
            shape.line.fill.background()
        return shape

    # ==========================================
    # SLIDE 1: TITLE SLIDE (Dark Hero)
    # ==========================================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_background(s1, DARK_BG)

    # Accent decorative banner
    accent = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.2), Inches(2.2), Inches(0.35))
    accent.fill.solid()
    accent.fill.fore_color.rgb = FOREST
    accent.line.fill.background()
    p_acc = accent.text_frame.paragraphs[0]
    p_acc.text = "IEEE HACKATHON 2026"
    p_acc.font.name = "Calibri"
    p_acc.font.size = Pt(11)
    p_acc.font.bold = True
    p_acc.font.color.rgb = WHITE
    p_acc.alignment = PP_ALIGN.CENTER

    tb1 = s1.shapes.add_textbox(Inches(0.8), Inches(1.7), Inches(11.7), Inches(2.5))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    p1 = tf1.paragraphs[0]
    p1.text = "UrbanGreen AI"
    p1.font.name = "Calibri"
    p1.font.size = Pt(54)
    p1.font.bold = True
    p1.font.color.rgb = WHITE

    p2 = tf1.add_paragraph()
    p2.text = "Autonomous Geospatial Intelligence & Satellite-Driven Green Interventions"
    p2.font.name = "Calibri"
    p2.font.size = Pt(22)
    p2.font.color.rgb = EMERALD
    p2.space_before = Pt(10)

    p3 = tf1.add_paragraph()
    p3.text = "Transforming raw earth observation, satellite reanalysis, and vector networks into actionable urban cooling and greening roadmaps."
    p3.font.name = "Calibri"
    p3.font.size = Pt(15)
    p3.font.color.rgb = RGBColor(180, 205, 190)
    p3.space_before = Pt(14)

    # Bottom Meta Card
    card_meta = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(5.2), Inches(11.7), Inches(1.5))
    card_meta.fill.solid()
    card_meta.fill.fore_color.rgb = RGBColor(22, 45, 33)
    card_meta.line.color.rgb = RGBColor(40, 75, 55)
    tf_meta = card_meta.text_frame
    tf_meta.word_wrap = True
    
    pm1 = tf_meta.paragraphs[0]
    pm1.text = "Track: Sustainable Living & Resilient Cities   |   Live Demo: urbangreen-ai.onrender.com/ui"
    pm1.font.name = "Calibri"
    pm1.font.size = Pt(14)
    pm1.font.bold = True
    pm1.font.color.rgb = WHITE

    pm2 = tf_meta.add_paragraph()
    pm2.text = "GitHub Repository: https://github.com/sunny-kumar-yadav-byte/urbangreen-ai"
    pm2.font.name = "Calibri"
    pm2.font.size = Pt(13)
    pm2.font.color.rgb = EMERALD
    pm2.space_before = Pt(6)

    # ==========================================
    # SLIDE 2: THE PROBLEM (Urban Heat Island & Blindspots)
    # ==========================================
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_background(s2, OFF_WHITE)
    add_header(s2, "The Challenge: Urban Heat Islands & Planning Blindspots")

    cols = [
        ("Extreme Heat Concentration", "Impervious concrete and dense road networks trap thermal radiation, creating urban heat islands with temperatures 3°C to 7°C above surrounding regions.", "🔥"),
        ("Lack of Micro-Grid Resolution", "Traditional municipal datasets measure city-wide macro averages, failing to pinpoint localized hotspots, lack of tree canopy, and vulnerable street corridors.", "📍"),
        ("Subjective & Delayed Interventions", "Urban greening projects frequently lack empirical prioritization. Green spaces are built where convenient, rather than where thermal relief is critically needed.", "📉")
    ]
    for i, (head, desc, icon) in enumerate(cols):
        left = Inches(0.8 + i * 3.95)
        card = add_card(s2, left, Inches(1.8), Inches(3.8), Inches(4.8))
        tf = card.text_frame
        tf.word_wrap = True
        
        pi = tf.paragraphs[0]
        pi.text = icon
        pi.font.size = Pt(36)
        
        ph = tf.add_paragraph()
        ph.text = head
        ph.font.name = "Calibri"
        ph.font.size = Pt(18)
        ph.font.bold = True
        ph.font.color.rgb = TEXT_DARK
        ph.space_before = Pt(14)

        pd = tf.add_paragraph()
        pd.text = desc
        pd.font.name = "Calibri"
        pd.font.size = Pt(13)
        pd.font.color.rgb = TEXT_MUTED
        pd.space_before = Pt(10)

    # ==========================================
    # SLIDE 3: OUR SOLUTION (UrbanGreen AI Engine)
    # ==========================================
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_background(s3, OFF_WHITE)
    add_header(s3, "The Solution: Automated Geospatial Micro-Climate Intelligence")

    features = [
        ("Real Satellite & Vector Acquisition", "Automated retrieval of live Land Surface Temperature (LST) from satellite reanalysis and OpenStreetMap building/road vector networks.", Inches(1.8)),
        ("Spatial Polygon Grid Partitioning", "Generates mathematically uniform 100m to 1000m planar polygonal grids, projecting WGS84 coordinates into real metric Cartesian space.", Inches(3.1)),
        ("Multi-Factor Priority Scoring", "Normalizes heat, vegetation deficit (1-NDVI), built-up ratio, road density, and solar exposure to classify zones into Low, Medium, and High priority.", Inches(4.4)),
        ("Actionable & Targeted Interventions", "Recommends tailored, rule-based environmental solutions (canopy expansion, cool roofs, bioswales, pocket parks) with quantifiable rationales.", Inches(5.7))
    ]
    for title, desc, top in features:
        card = add_card(s3, Inches(0.8), top, Inches(11.7), Inches(1.15))
        tf = card.text_frame
        tf.word_wrap = True
        pt = tf.paragraphs[0]
        pt.text = "• " + title
        pt.font.name = "Calibri"
        pt.font.size = Pt(16)
        pt.font.bold = True
        pt.font.color.rgb = FOREST

        pd = tf.add_paragraph()
        pd.text = "   " + desc
        pd.font.name = "Calibri"
        pd.font.size = Pt(13)
        pd.font.color.rgb = TEXT_MUTED
        pd.space_before = Pt(3)

    # ==========================================
    # SLIDE 4: SYSTEM ARCHITECTURE
    # ==========================================
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_background(s4, OFF_WHITE)
    add_header(s4, "End-to-End System Architecture")

    arch_layers = [
        ("Layer 1: Geospatial Ingestion", ["• Open-Meteo Satellite Reanalysis (Live LST)", "• OSM Overpass API (Buildings & Roads)", "• Google Earth Engine API Connector", "• Custom GIS Shapefile/GeoJSON Ingestion"], Inches(0.8)),
        ("Layer 2: Spatial & Vector Engine", ["• Coordinate Geocoding & Bounding Box Extraction", "• Planar UTM Metric Projector (Shapely + PyProj)", "• Adaptive 4-Quadrant Chunking & Deduplication", "• STRtree Spatial Indexing for Fast Intersections"], Inches(4.75)),
        ("Layer 3: Analytical Delivery", ["• Reference & Relative Feature Normalization", "• Weighted Rule-Based Priority Scoring Engine", "• GeoJSON Polygon RFC 7946 Layer Generator", "• Leaflet Interactive Map & Scenario Simulator"], Inches(8.7))
    ]
    for title, items, left in arch_layers:
        card = add_card(s4, left, Inches(1.8), Inches(3.8), Inches(4.8))
        tf = card.text_frame
        tf.word_wrap = True
        pt = tf.paragraphs[0]
        pt.text = title
        pt.font.name = "Calibri"
        pt.font.size = Pt(16)
        pt.font.bold = True
        pt.font.color.rgb = FOREST

        for it in items:
            pi = tf.add_paragraph()
            pi.text = it
            pi.font.name = "Calibri"
            pi.font.size = Pt(12)
            pi.font.color.rgb = TEXT_DARK
            pi.space_before = Pt(8)

    # ==========================================
    # SLIDE 5: ENGINEERING INNOVATION - ADAPTIVE CHUNKING
    # ==========================================
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_background(s5, OFF_WHITE)
    add_header(s5, "Engineering Breakthrough: Adaptive Spatial Quadrant Chunking")

    c1 = add_card(s5, Inches(0.8), Inches(1.8), Inches(5.7), Inches(4.8))
    tf1 = c1.text_frame
    tf1.word_wrap = True
    p = tf1.paragraphs[0]
    p.text = "The Overpass Bottleneck"
    p.font.name = "Calibri"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = ACCENT_ORANGE

    p = tf1.add_paragraph()
    p.text = "Dense metropolitan cities contain staggering numbers of structures (e.g. New York has >322,000 building ways across ~320 km²).\n\nSingle monolithic queries to public Overpass servers trigger HTTP 504 Gateway Timeouts or Apache buffer overflows, causing complete pipeline failure."
    p.font.name = "Calibri"
    p.font.size = Pt(13)
    p.font.color.rgb = TEXT_MUTED
    p.space_before = Pt(10)

    c2 = add_card(s5, Inches(6.8), Inches(1.8), Inches(5.7), Inches(4.8))
    tf2 = c2.text_frame
    tf2.word_wrap = True
    p = tf2.paragraphs[0]
    p.text = "Our Adaptive Chunking Solution"
    p.font.name = "Calibri"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = FOREST

    points = [
        "1. Dynamic Thresholding: Bounding boxes >0.15° (~16 km) are automatically partitioned into 4 non-overlapping quadrants (SW, SE, NW, NE).",
        "2. Boundary Deduplication: Cross-border structures are indexed and deduplicated by unique OSM Element ID, preventing artificial polygon inflation.",
        "3. Partial Recovery & Integrity: Successfully fetched quadrants are retained and calculated. Failures are transparently reported in metadata warnings without silent synthetic substitution."
    ]
    for pt_text in points:
        pi = tf2.add_paragraph()
        pi.text = pt_text
        pi.font.name = "Calibri"
        pi.font.size = Pt(12)
        pi.font.color.rgb = TEXT_DARK
        pi.space_before = Pt(8)

    # ==========================================
    # SLIDE 6: FORMULA & MULTI-FACTOR SCORING
    # ==========================================
    s6 = prs.slides.add_slide(blank_layout)
    set_slide_background(s6, OFF_WHITE)
    add_header(s6, "Analytical Methodology: Environmental Decision Index")

    card_formula = add_card(s6, Inches(0.8), Inches(1.8), Inches(11.7), Inches(1.3), bg_color=LIGHT_GREEN, border_color=FOREST)
    tf_f = card_formula.text_frame
    tf_f.word_wrap = True
    pf1 = tf_f.paragraphs[0]
    pf1.text = "Priority Score = 0.35·Heat + 0.25·BuiltUp + 0.15·RoadDensity + 0.15·Exposure + 0.10·(1 - NDVI)"
    pf1.font.name = "Calibri"
    pf1.font.size = Pt(18)
    pf1.font.bold = True
    pf1.font.color.rgb = FOREST
    pf1.alignment = PP_ALIGN.CENTER

    pf2 = tf_f.add_paragraph()
    pf2.text = "All input indicators are scaled to [0.0, 1.0] using regional reference bounds to enable equitable cross-city comparison."
    pf2.font.name = "Calibri"
    pf2.font.size = Pt(12)
    pf2.font.color.rgb = TEXT_DARK
    pf2.alignment = PP_ALIGN.CENTER
    pf2.space_before = Pt(4)

    weights_data = [
        ("Heat Index (35%)", "Land Surface Temperature (°C) relative to climate baselines (18°C–48°C)."),
        ("Built-Up Ratio (25%)", "Real polygon building footprint coverage per grid cell area."),
        ("Road Density (15%)", "Total road length in cell divided by cell area, normalized to 25 km/km² ceiling."),
        ("Solar Exposure (15%)", "Thermal and solar vulnerability compounded by high imperviousness."),
        ("Vegetation Deficit (10%)", "Complement of NDVI (1.0 - NDVI), highlighting canopy-deficient barren parcels.")
    ]
    for i, (w_title, w_desc) in enumerate(weights_data):
        top = Inches(3.3 + i * 0.75)
        w_card = add_card(s6, Inches(0.8), top, Inches(11.7), Inches(0.65))
        tf_w = w_card.text_frame
        tf_w.word_wrap = True
        p_w = tf_w.paragraphs[0]
        p_w.text = f"{w_title}: {w_desc}"
        p_w.font.name = "Calibri"
        p_w.font.size = Pt(13)
        p_w.font.color.rgb = TEXT_DARK

    # ==========================================
    # SLIDE 7: RULE-BASED GREEN INTERVENTIONS
    # ==========================================
    s7 = prs.slides.add_slide(blank_layout)
    set_slide_background(s7, OFF_WHITE)
    add_header(s7, "Targeted Greening Interventions & Policy Categorization")

    tiers = [
        ("CRITICAL / HIGH PRIORITY (Score >= 0.66)", [
            "• Intensive Urban Forest Expansion: Rapid planting of native dense canopy in severe heat corridors.",
            "• High-Albedo Cool Roofs & Pavements: Mandating solar-reflective coatings on building surfaces.",
            "• Micro-Woodland Corridors: Establishing continuous pocket biomes to induce convective cooling."
        ], RGBColor(248, 230, 228), RGBColor(183, 68, 61)),
        ("MEDIUM PRIORITY (0.33 <= Score < 0.66)", [
            "• Bioswales & Vegetated Road Buffers: Integrating roadside rain gardens along dense road links.",
            "• Neighborhood Pocket Parks: Reclaiming underutilized vacant lots for localized shade.",
            "• Permeable Pavers: Enhancing soil infiltration and ground thermal discharge."
        ], RGBColor(248, 240, 223), RGBColor(179, 122, 32)),
        ("LOW / STABLE PRIORITY (Score < 0.33)", [
            "• Canopy Preservation Protocols: Protective monitoring of mature tree health and foliage.",
            "• Ecological Sensor Monitoring: Baseline environmental tracking to maintain current balance.",
            "• Native Groundcover Stewardship: Supporting community gardening and biodiversity."
        ], RGBColor(229, 240, 232), RGBColor(75, 128, 96))
    ]
    for i, (title, items, bg_col, text_col) in enumerate(tiers):
        top = Inches(1.8 + i * 1.75)
        card = add_card(s7, Inches(0.8), top, Inches(11.7), Inches(1.55), bg_color=bg_col, border_color=text_col)
        tf = card.text_frame
        tf.word_wrap = True
        pt = tf.paragraphs[0]
        pt.text = title
        pt.font.name = "Calibri"
        pt.font.size = Pt(15)
        pt.font.bold = True
        pt.font.color.rgb = text_col

        for it in items:
            pi = tf.add_paragraph()
            pi.text = it
            pi.font.name = "Calibri"
            pi.font.size = Pt(12)
            pi.font.color.rgb = TEXT_DARK
            pi.space_before = Pt(3)

    # ==========================================
    # SLIDE 8: WHAT-IF SIMULATOR
    # ==========================================
    s8 = prs.slides.add_slide(blank_layout)
    set_slide_background(s8, OFF_WHITE)
    add_header(s8, "Interactive 'What-If' Scenario Simulation Engine")

    c_left = add_card(s8, Inches(0.8), Inches(1.8), Inches(5.7), Inches(4.8))
    tf_l = c_left.text_frame
    tf_l.word_wrap = True
    p = tf_l.paragraphs[0]
    p.text = "How the Simulator Works"
    p.font.name = "Calibri"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = FOREST

    points_sim = [
        "• Planners select an active grid zone (e.g. Z014).",
        "• Custom slider inputs simulate proposed green interventions: reducing surface heat by 20% or increasing canopy cover (NDVI +0.35).",
        "• POST /what-if immediately recalculates the multi-factor weighted equation in milliseconds.",
        "• Outputs the exact delta (score change), category transition (High -> Medium), and updated intervention priorities."
    ]
    for pt in points_sim:
        pi = tf_l.add_paragraph()
        pi.text = pt
        pi.font.name = "Calibri"
        pi.font.size = Pt(13)
        pi.font.color.rgb = TEXT_DARK
        pi.space_before = Pt(8)

    c_right = add_card(s8, Inches(6.8), Inches(1.8), Inches(5.7), Inches(4.8), bg_color=CARD_BG)
    tf_r = c_right.text_frame
    tf_r.word_wrap = True
    p = tf_r.paragraphs[0]
    p.text = "Real Scenario Simulation Example"
    p.font.name = "Calibri"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = TEXT_DARK

    eg = [
        ("Target Zone", "Zone Z001 (Bhopal Metropolitan Grid)"),
        ("Baseline Metrics", "Heat: 0.65 | NDVI: 0.22 | Built-Up: 0.70"),
        ("Baseline Score", "0.4532 (MEDIUM Priority)"),
        ("Simulated Action", "Tree Canopy Expansion (+0.48 NDVI) & Cool Pavements (-0.20 Heat)"),
        ("Updated Score", "0.3382 (Score Change: -0.1150)"),
        ("Revised Directive", "Transitioned to Stable Maintenance")
    ]
    for k, v in eg:
        p_eg = tf_r.add_paragraph()
        p_eg.text = f"{k}: {v}"
        p_eg.font.name = "Calibri"
        p_eg.font.size = Pt(12)
        p_eg.font.color.rgb = TEXT_MUTED if "Metrics" in k else TEXT_DARK
        if "Updated" in k or "Target" in k:
            p_eg.font.bold = True
        p_eg.space_before = Pt(5)

    # ==========================================
    # SLIDE 9: VERIFICATION & TESTING RIGOR
    # ==========================================
    s9 = prs.slides.add_slide(blank_layout)
    set_slide_background(s9, OFF_WHITE)
    add_header(s9, "Software Quality & Verification Rigor")

    test_cards = [
        ("30 / 30 Passed", "Complete pytest test suite with 100% pass rate across API, pipeline, and satellite services.", FOREST),
        ("Adaptive Resilience", "Mocked tests for Overpass HTTP 504 recovery, HTTP 406 headers, and cross-boundary deduplication.", FOREST),
        ("Zero Fabrication", "Verified that incomplete requests report explicit metadata warnings rather than silently substituting synthetic data.", FOREST),
        ("Global Benchmark Validation", "Live testing validated across major global benchmark cities: Bhopal, Delhi, Paris, and New York.", FOREST)
    ]
    for i, (title, desc, color) in enumerate(test_cards):
        col_idx = i % 2
        row_idx = i // 2
        left = Inches(0.8 + col_idx * 5.95)
        top = Inches(1.8 + row_idx * 2.5)
        card = add_card(s9, left, top, Inches(5.75), Inches(2.3))
        tf = card.text_frame
        tf.word_wrap = True
        pt = tf.paragraphs[0]
        pt.text = title
        pt.font.name = "Calibri"
        pt.font.size = Pt(20)
        pt.font.bold = True
        pt.font.color.rgb = color

        pd = tf.add_paragraph()
        pd.text = desc
        pd.font.name = "Calibri"
        pd.font.size = Pt(13)
        pd.font.color.rgb = TEXT_MUTED
        pd.space_before = Pt(8)

    # ==========================================
    # SLIDE 10: CONCLUSION & DEMO LINKS
    # ==========================================
    s10 = prs.slides.add_slide(blank_layout)
    set_slide_background(s10, DARK_BG)

    tb10 = s10.shapes.add_textbox(Inches(0.8), Inches(1.2), Inches(11.7), Inches(2.0))
    tf10 = tb10.text_frame
    tf10.word_wrap = True
    p = tf10.paragraphs[0]
    p.text = "Empowering Climate-Resilient Cities"
    p.font.name = "Calibri"
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = WHITE

    p = tf10.add_paragraph()
    p.text = "UrbanGreen AI bridges the gap between complex Earth observation rasters and actionable, street-level municipal greening policies."
    p.font.name = "Calibri"
    p.font.size = Pt(18)
    p.font.color.rgb = EMERALD
    p.space_before = Pt(8)

    c_links = s10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(3.6), Inches(11.7), Inches(2.8))
    c_links.fill.solid()
    c_links.fill.fore_color.rgb = RGBColor(22, 45, 33)
    c_links.line.color.rgb = RGBColor(40, 75, 55)
    tf_l = c_links.text_frame
    tf_l.word_wrap = True

    p = tf_l.paragraphs[0]
    p.text = "Project Resources & Live Links"
    p.font.name = "Calibri"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = WHITE

    links_info = [
        ("Live Interactive Web App", "https://urbangreen-ai.onrender.com/ui"),
        ("Interactive API Docs (Swagger)", "https://urbangreen-ai.onrender.com/docs"),
        ("GitHub Open-Source Repository", "https://github.com/sunny-kumar-yadav-byte/urbangreen-ai"),
        ("System Architecture & Tests", "30 passing automated tests | FastAPI + Leaflet + GeoJSON")
    ]
    for label, val in links_info:
        p = tf_l.add_paragraph()
        p.text = f"• {label}: {val}"
        p.font.name = "Calibri"
        p.font.size = Pt(13)
        p.font.color.rgb = EMERALD if "http" in val else WHITE
        p.space_before = Pt(6)

    prs.save(output_path)
    print(f"Presentation saved successfully to: {output_path}")

if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "UrbanGreen_AI_Presentation.pptx"
    create_deck(out_file)
