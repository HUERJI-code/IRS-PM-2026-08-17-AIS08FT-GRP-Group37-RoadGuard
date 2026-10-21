# Project report

The current [group Final Report](IRS-PM-2026-08-17-AIS08FT-GRP-Group7-RoadGuard-Group-Report.docx) includes English screenshots captured on 19 October 2026. The Markdown files are supporting outlines and guides. The 20 October installation correction specifies Python 3.12 for the full vision environment because NumPy 2.5.2 requires Python >=3.12; Python 3.11 CI installs only the base dependency set. The 21 October update incorporates the delivered assistant and persistent task adjustments. Repository and Assignment copies are synchronized.

The report is 42 pages: three preliminary pages, 18 pages across six main chapters, the complete seven-page installation and user guide in Appendix A, all 13 pages of the final submitted proposal in Appendix B, and a one-page course-functionality mapping in Appendix C. Repeated main-text material has been consolidated while retaining key experiments, failure analysis and team contributions. Vision metrics and their limitations appear in the results chapter rather than the abstract, with proposed improvements in the final chapter. The 32 linked contents entries include all three appendices and all nine user-guide subsections, with verified page numbers. Every rendered page was visually inspected; all original embedded images, including the submitted proposal, are preserved.

Its dispatcher review and mobile crew screenshots show the running English interface. The captures use an isolated test database and synthetic detection scenarios, not a new model-quality evaluation.

The report includes all three appendix categories explicitly requested by the practice briefing. Section 1.3 retains the comparison between the original plan and delivered scope and refers to Appendix B for the historical proposal. Section 3.4 explains how the reasoning methods work together and refers to Appendix C for the MR/RS/CGS evidence mapping. The mapping points to existing design and evaluation sections instead of repeating their results. This document coverage does not imply that outstanding functionality, videos or other submission items are complete.

- [English dispatcher review screenshot](figures/reviews-desktop-en.jpg)
- [English mobile crew screenshot](figures/crew-mobile-en.jpg)

- [Report outline](REPORT_OUTLINE.md)
- [Installation and user guide](INSTALLATION_AND_USER_GUIDE.md)
- [Course technique mapping](COURSE_MAPPING.md)
- [Final submitted proposal archive](Proposal/RoadGuard_ProjectProposal.pdf), with [archive notes](Proposal/README.md) and a separate [scope addendum](../Miscellaneous/PROJECT_SCOPE.md).
- `figures/`: diagrams, screenshots and measured evaluation figures.

Do not edit the historical submitted proposal to imply that the four-crew scope was part of its original submission. Document the presentation feedback and resulting scope change separately.

The architecture, implementation, bounded assistant evaluation and future-work sections now describe ChromaDB/E5, query-v3 response modes, source validation, confirmed task reassignment/cancellation, persistent crew constraints and explicit replanning. Historical vision/routing numbers remain unchanged. PR 36 CI and targeted real-provider results are recorded separately from earlier checks; overlapping test counts are not added. See the [release record](../Miscellaneous/RAG_TASK_RELEASE_20261021.md).
