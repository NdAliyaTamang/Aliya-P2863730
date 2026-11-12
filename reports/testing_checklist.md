# OwnableFit Testing Checklist

This record distinguishes automated checks, developer-reported manual
checks and work that remains outstanding.

Passing software tests does not establish prediction accuracy,
correct fit, reduced returns or complete accessibility/security.

## Test environment

- Computer: development Mac
- Python: 3.13.15
- Main environment: .venv-model
- Separate installation-check environment: .venv-check
- Dependencies: requirements-web.txt
- Browser and version: not yet recorded
- Manual test date: not yet recorded

## Automated checks

Run from the project root:

python -m unittest discover -s tests -v

| Checkpoint | Result | Scope |
|---|---|---|
| Main development environment | 52 tests passed | Prediction, pages, validation, catalogue and sustainability |
| Fresh dependency installation | Installation succeeded | Same Mac, separate .venv-check environment |
| Dependency consistency | pip check passed | No broken requirements reported |
| Tests in fresh environment | 40 tests passed | Before catalogue features were added |

The latest 52-test suite has not yet been verified in .venv-check.

Saved test output:
reports/integration_test_results.txt

The saved output should be checked after each deliberate evidence update.
Some tests use mocked outputs to isolate application behaviour.
Real-model integration is checked separately within the suite.

## Manual functional checks

These results were reported by the developer during guided testing.

| Journey | Status | Observation |
|---|---|---|
| Open dashboard | Passed | Dashboard loads and shows model coverage |
| Navigate between pages | Passed | Implemented pages open through navigation |
| Active-page indication | Passed | Current page is highlighted |
| Search catalogue | Passed | Known dress ID can be found |
| Select catalogue item | Passed | Selected ID appears in recommendation form |
| Submit illustrative prediction | Passed | Dress 1000254, height 165, weight 62, bra size 34b returns code 8 |
| Identify result item | Passed | Result identifies the submitted dress |
| Empty form | Passed | Browser requests a required selection |
| Negative height | Passed | Browser blocks submission |
| Expand measurement guidance | Verification pending | Feature implemented; explicit outcome not recorded |
| Clear and start again | Verification pending | Automated fresh-form check passes; explicit manual outcome not recorded |
| Single sustainability scenario | Passed | Illustrative inputs return expected values |
| Compare scenarios | Passed | Illustrative low/medium/high reductions produce 10, 20 and 40 expected avoided returns |

The prediction example is a technical integration check,
not evidence that code 8 fits a real customer.

## Keyboard and layout checks

| Check | Status | Limit |
|---|---|---|
| Tab navigation | Passed as reported | Browser/version not recorded |
| Complete journey without a mouse | Verification pending | Selection and submission were not explicitly confirmed |
| Visible focus on every interactive control | Verification pending | Requires deliberate inspection |
| Narrow browser window | Passed as reported | No overlap or clipping reported |
| Real phone testing | Not completed | Narrow desktop window is not equivalent to a physical-device test |
| Screen-reader testing | Not completed | No accessibility compliance claim |
| Browser zoom at 200% | Not completed | Check readability and control access |
| Additional browser | Not completed | Browser compatibility remains unverified |

## Research and interpretation limits

- Output is an original dataset size code.
- No US/EU size conversion has been verified.
- Product photographs and retail details are not verified.
- Numeric validation checks finite, positive measurements.
- Development-data range checking is not implemented.
- Held-out accuracy is 43.73%.
- Reported fixed-label macro F1 is 0.1639.
- These metrics are not personal probabilities of fit.
- Evaluation mainly concerns new customers on known dresses.
- The traditional size-chart comparison remains unresolved.
- Fairness analysis requires review of the research evidence.
- Sustainability results are hypothetical calculations.
- Emissions factors and scenario assumptions need documented sources.

## Privacy and security scope

The implemented code avoids deliberately saving body measurements
to customer profiles, prediction histories or application logs.

Forms submit measurements using POST.
Application responses include Cache-Control: no-store.

These implementation choices do not demonstrate complete privacy
or security. The application has not undergone a full security audit
and is configured for local development only.

## Outstanding verification

- Record browser name/version and manual test dates.
- Confirm the full keyboard-only recommendation journey.
- Confirm focus visibility and 200% zoom behaviour.
- Test on a real phone and an additional browser.
- Obtain feedback from people other than the developer.
- Record feedback, fixes and follow-up checks.
- Run the latest 52 tests in the separate environment.
- Update README.md to describe the catalogue and latest test checkpoint.
- Review unresolved research requirements in the research-audit chat.