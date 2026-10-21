# Submission checklist

Source of current requirements: practice module briefing v2.17, pages 6, 9, 10, 13 and 14. See [source notes](TEMPLATE_SOURCE.md).

## Repository setup

- [x] Template's four main directories: `SystemCode`, `ProjectReport`, `Video`, `Miscellaneous`.
- [x] README's seven sections adapted to RoadGuard.
- [x] Four-crew/Jurong scope recorded.
- [x] Course start date 2026-08-17 and batch code AIS08FT confirmed; use Group7 for the group number.
- [x] Private GitHub repository created and URL recorded.
- [ ] Assessor access arranged as required by the course.
- [x] Team roster and contribution table populated from final report Table 5 in the root README.

## Group deliverables

- [x] Runnable local prototype with recorded integration acceptance; independent clean-machine installation remains unchecked below.
- [x] Three technique groups mapped to implementation and recorded evidence in Appendix C; final assessment remains with the course assessors.
- [ ] Five-minute promotion/use-case video.
- [ ] Separate five-minute system-design/technical video.
- [x] Group report available as DOCX, with business case, design, implementation, experiments, findings and discussion.
- [x] Report appendix: final submitted project proposal in Appendix B; subsequent scope changes in Section 1.3.
- [x] Report appendix: functionality-to-MR/RS/CGS mapping in Appendix C, linked to implementation and recorded verification evidence.
- [x] Report appendix: installation and user guide; full-vision environment corrected to Python 3.12.
- [ ] Independently validate installation on a clean machine; current evidence covers the recorded local environment and base CI.
- [ ] `member-github.txt`: group name, official member names, student IDs or permitted masked identifiers, GitHub URL.
- [ ] Downloaded repository ZIP.
- [ ] Final ZIP containing the roster file, both videos, repository ZIP and group report.

## Naming

Use `IRS-PM-2026-08-17-AIS08FT-GRP-Group7-RoadGuard` as the common prefix.

- Promotion video: `<prefix>-promotion.mp4`
- System video: `<prefix>-system.mp4`
- Repository archive: `<prefix>.zip`
- Group report: `<prefix>-Group-Report.pdf` (or DOCX)
- Final submission archive: `<prefix>.zip`, saved separately from the repository archive.

Prepare the actual `member-github.txt` outside version control using the example file. It belongs in the final group submission package.

## Individual submission

- [ ] Each member completes the individual reflection and peer-review form.
- [ ] Each member submits confidentially through the separate individual Canvas assignment.

The current briefing states a final deadline of **2026-10-25 at 23:59**. Check Canvas for any later course announcement. Presentation speech must not be AI-generated, per the current briefing.

## Current assistant release evidence

The current source includes local ChromaDB/E5 retrieval, query-v3 English grounded answers, default-closed sources and confirmed persistent task adjustments. Targeted real GPT, isolated HTTP and browser acceptance is recorded in the [assistant intent](RAG_INTENT_ROUTING_ACCEPTANCE_20261021.md) and [task-adjustment](TASK_ADJUSTMENT_ACCEPTANCE_20261021.md) records. These records are not a broad accuracy benchmark. Keep the final report, full Appendix A guide and course mapping synchronized with knowledge-v17; verify final report pagination after rendering. Clean-machine installation and video/package checks above remain outstanding.
