# Disclaimer

`ccsds-data-messages` is provided as-is, for the purpose of reading, writing, and
validating the structure of CCSDS Orbit Data Messages. It is a data-handling library,
not a source of authoritative orbital information.

**No guarantee of accuracy or fitness.** The library does not guarantee that the
messages it produces or parses are correct, complete, or fit for any particular
purpose. Passing validation means a message conforms to the structural rules the
library implements; it does not mean the numbers in that message are physically
accurate, current, or safe to act on. Conformance checking is best-effort and may
contain errors or omissions relative to the CCSDS standard.

**Not for safety-critical or operational use without independent verification.** This
software must not be relied on as the sole basis for any operational, navigational,
flight-dynamics, collision-avoidance, conjunction-assessment, or debris-tracking
decision. You are solely responsible for independently verifying every input and output
before using it for any real-world purpose.

**No liability.** To the maximum extent permitted by law, the authors, contributors,
and Loft Orbital Solutions Inc. accept no liability for any loss, damage, injury, or
cost of any kind (including, without limitation, loss of or damage to spacecraft,
collisions, mistracked or untracked debris, service interruption, or loss of data)
arising out of or in connection with the use of, or reliance on, this software, whether
in contract, tort, or otherwise.

This notice complements, and does not replace, the "Disclaimer of Warranty" and
"Limitation of Liability" sections of the Apache License, Version 2.0, under which this
software is distributed. See the
[LICENSE](https://github.com/open-space-collective/ccsds-data-messages/blob/main/LICENSE)
for the full terms.
