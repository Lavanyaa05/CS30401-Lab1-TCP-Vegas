#include "adaptive-basertt-detector.h"
#include <cassert>

int main()
{
    constexpr long long base = 80000000;
    ns3::AdaptiveBaseRttDetector d;
    // Strict threshold: below and exactly 3 ms never qualify.
    assert(!d.Observe(0, base + 2999999, base));
    assert(!d.Observe(1, base + 3000000, base));
    for (int i = 0; i < 4; ++i) assert(!d.Observe(100000000 + i, base + 3000001, base));
    assert(d.Observe(200000000, base + 3000001, base));
    assert(d.shiftCount == 0);
    // Cooldown: below and exactly 10 s reset persistence to zero.
    assert(!d.Observe(10199999999LL, base + 4000000, base));
    assert(!d.Observe(10200000000LL, base + 4000000, base));
    assert(d.shiftCount == 0);
    for (int i = 1; i < 5; ++i) assert(!d.Observe(10200000000LL + i, base + 4000000, base));
    assert(d.Observe(10200000005LL, base + 4000000, base));
    ns3::AdaptiveBaseRttDetector transient;
    for (int i = 0; i < 4; ++i) assert(!transient.Observe(i, base + 4000000, base));
    assert(!transient.Observe(5, base + 3000000, base));
    assert(transient.shiftCount == 0);
    // Eligible calls only: omitted/recovery cycles do not modify prototype state.
    assert(!transient.Observe(6, base + 4000000, base));
    assert(transient.shiftCount == 1);
    // An ordinary downward minimum update produces no upward qualification.
    assert(!transient.Observe(7, base - 1000000, base - 1000000));
    assert(transient.shiftCount == 0);
    ns3::AdaptiveBaseRttDetector independent;
    assert(independent.lastResetNs == -1000000000000LL);
    assert(!independent.Observe(0, base + 4000000, base));
    assert(independent.shiftCount == 1 && d.shiftCount == 0);
    // Fork copies prototype state, then remains independent.
    auto fork = independent;
    assert(!fork.Observe(1, base + 4000000, base));
    assert(fork.shiftCount == 2 && independent.shiftCount == 1);
}
