"""Built-in sample study notes, served for the "Try a sample document" button and used by tests.

Generated on demand (and cached) so the repository contains no binary files.
"""

import io
from functools import lru_cache

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer

H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=20, leading=26, spaceAfter=8)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=14, leading=19, spaceBefore=10, spaceAfter=6, textColor=colors.HexColor("#1e3a8a"))
BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=11, leading=16, spaceAfter=6)

CONTENT = [
    ("h1", "Photosynthesis — Revision Notes (Class 11 Biology)"),
    ("p", "Photosynthesis is the process by which green plants, algae and some bacteria convert light energy into chemical energy. "
          "The energy is stored in glucose, which the plant uses for respiration, growth and making other organic molecules. "
          "Photosynthesis also releases oxygen, which almost all living organisms need for aerobic respiration."),
    ("p", "The overall balanced equation is: 6CO2 + 6H2O + light energy → C6H12O6 + 6O2. Carbon dioxide is taken in through "
          "the stomata of leaves, and water is absorbed by the roots and transported to the leaves through the xylem."),
    ("h2", "1. The Chloroplast"),
    ("p", "Photosynthesis takes place in chloroplasts, which are found mainly in the mesophyll cells of leaves. A chloroplast is "
          "surrounded by a double membrane called the envelope. Inside, it contains a fluid-filled matrix called the stroma and a "
          "system of flattened membrane sacs called thylakoids."),
    ("p", "Thylakoids are stacked into structures called grana (singular: granum). The thylakoid membranes contain the "
          "photosynthetic pigments, the electron transport chain and the enzyme ATP synthase. The stroma contains the enzymes "
          "of the Calvin cycle, including RuBisCO, as well as starch grains, ribosomes and circular DNA."),
    ("list", [
        "Chlorophyll a is the primary pigment found in the reaction centres of the photosystems.",
        "Chlorophyll b and carotenoids are accessory pigments that absorb other wavelengths and pass energy to chlorophyll a.",
        "Chlorophyll absorbs mainly red and blue light and reflects green light, which is why leaves look green.",
    ]),
    ("h2", "2. The Light-Dependent Reactions"),
    ("p", "The light-dependent reactions take place on the thylakoid membranes. Their purpose is to convert light energy into "
          "chemical energy in the form of ATP and NADPH, which are then used in the Calvin cycle."),
    ("p", "When light strikes photosystem II, it excites electrons in chlorophyll to a higher energy level. These electrons are "
          "passed along an electron transport chain. As they move, they release energy that is used to pump hydrogen ions (H+) "
          "into the thylakoid space, creating a concentration gradient."),
    ("p", "To replace the electrons lost from photosystem II, water molecules are split in a process called photolysis. "
          "Photolysis releases oxygen as a by-product, together with hydrogen ions and electrons. The hydrogen ions flow back into "
          "the stroma through ATP synthase, and this flow drives the production of ATP. This process is called photophosphorylation."),
    ("p", "The electrons are re-energised at photosystem I and finally reduce NADP+ to form NADPH. In cyclic photophosphorylation, "
          "electrons from photosystem I return to the electron transport chain instead, producing ATP but no NADPH and no oxygen."),
    ("pagebreak", ""),
    ("h2", "3. The Calvin Cycle (Light-Independent Reactions)"),
    ("p", "The Calvin cycle takes place in the stroma and does not directly need light, although it depends on the ATP and NADPH "
          "made in the light-dependent reactions. It is sometimes called the light-independent reaction or dark reaction, but it "
          "normally happens during the day."),
    ("p", "The cycle has three main stages:"),
    ("list", [
        "Carbon fixation: the enzyme RuBisCO combines carbon dioxide with ribulose bisphosphate (RuBP), a 5-carbon compound, producing two molecules of glycerate 3-phosphate (GP).",
        "Reduction: GP is reduced to triose phosphate (TP) using energy from ATP and hydrogen from NADPH.",
        "Regeneration: most of the triose phosphate is used to regenerate RuBP using ATP, so the cycle can continue.",
    ]),
    ("p", "For every six molecules of carbon dioxide fixed, the cycle produces one molecule of glucose. Only one in every six triose "
          "phosphate molecules leaves the cycle to make glucose, sucrose, starch, amino acids and lipids."),
    ("p", "RuBisCO is thought to be the most abundant protein on Earth. However, it is slow and can also react with oxygen instead "
          "of carbon dioxide, a wasteful process called photorespiration."),
    ("h2", "4. Limiting Factors"),
    ("p", "The rate of photosynthesis is controlled by limiting factors. A limiting factor is the factor that is in the shortest "
          "supply and therefore limits the rate of the process. The three main limiting factors are light intensity, carbon "
          "dioxide concentration and temperature."),
    ("list", [
        "Light intensity: increasing light intensity increases the rate until another factor becomes limiting.",
        "Carbon dioxide concentration: more CO2 increases the rate of carbon fixation by RuBisCO, up to a point.",
        "Temperature: the Calvin cycle is controlled by enzymes, so the rate rises with temperature until enzymes begin to denature, usually above about 40 °C.",
    ]),
    ("p", "Greenhouse growers use this knowledge to increase crop yields by adding artificial lighting, burning fuel to raise carbon "
          "dioxide levels and keeping the temperature at an optimum level."),
    ("h2", "5. C4 and CAM Plants"),
    ("p", "Plants that fix carbon dioxide directly with RuBisCO are called C3 plants, because the first stable product (GP) has three "
          "carbon atoms. In hot, dry conditions C3 plants close their stomata to save water, so oxygen builds up in the leaf and "
          "photorespiration increases."),
    ("p", "C4 plants such as maize and sugarcane avoid this problem. They first fix carbon dioxide in mesophyll cells using the enzyme "
          "PEP carboxylase, which does not react with oxygen, forming a 4-carbon compound. This compound is moved to bundle sheath "
          "cells, where carbon dioxide is released at high concentration for the Calvin cycle."),
    ("p", "CAM plants such as cacti and pineapple separate the steps in time instead of space. They open their stomata at night to take "
          "in carbon dioxide and store it as organic acids, then close their stomata during the day and release the carbon dioxide "
          "for the Calvin cycle. This greatly reduces water loss in desert conditions."),
    ("h2", "6. Measuring the Rate of Photosynthesis"),
    ("p", "The rate of photosynthesis can be measured by recording how quickly oxygen is produced or how quickly carbon dioxide is "
          "used up. A common school experiment uses pondweed such as Elodea placed in a test tube of water containing sodium "
          "hydrogen carbonate, which provides a supply of carbon dioxide."),
    ("p", "A lamp is placed at different distances from the pondweed, and the number of oxygen bubbles released per minute is counted. "
          "Because light intensity is inversely proportional to the square of the distance from the light source, moving the lamp "
          "twice as far away reduces the light intensity to one quarter."),
    ("list", [
        "Independent variable: light intensity (changed by moving the lamp).",
        "Dependent variable: the rate of oxygen production (bubbles per minute or volume of gas collected).",
        "Control variables: temperature, carbon dioxide concentration and the type and size of pondweed.",
    ]),
    ("p", "A more accurate method collects the gas in a photosynthometer (a capillary tube) and measures its volume, because bubbles "
          "can vary in size. A beaker of water placed between the lamp and the plant acts as a heat shield, keeping the temperature "
          "constant so that only light intensity is being tested."),
]


@lru_cache(maxsize=1)
def sample_pdf() -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
                            title="Photosynthesis — Revision Notes", author="StudyForge sample", invariant=1)
    story = []
    for kind, value in CONTENT:
        if kind == "h1":
            story.append(Paragraph(value, H1))
        elif kind == "h2":
            story.append(Paragraph(value, H2))
        elif kind == "p":
            story.append(Paragraph(value, BODY))
        elif kind == "list":
            story.append(ListFlowable([ListItem(Paragraph(v, BODY)) for v in value], bulletType="bullet", leftIndent=14))
            story.append(Spacer(1, 4))
        elif kind == "pagebreak":
            story.append(PageBreak())
    doc.build(story)
    return buf.getvalue()
