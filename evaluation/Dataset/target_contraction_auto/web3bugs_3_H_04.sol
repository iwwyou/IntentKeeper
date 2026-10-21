pragma solidity ^0.8.0;

struct HourlyBond {
    uint256 amount;
    uint256 yieldQuotientFP;
    uint256 moduloHour;
}

abstract contract HourlyBondSubscriptionLending is BaseLending {
    struct HourlyBondMetadata {
        YieldAccumulator yieldAccumulator;
        uint256 buyingSpeed;
        uint256 withdrawingSpeed;
        uint256 lastBought;
        uint256 lastWithdrawn;
    }

    mapping(address => HourlyBondMetadata) hourlyBondMetadata;

    uint256 public withdrawalWindow = 10 minutes;
    mapping(address => mapping(address => HourlyBond)) public hourlyBondAccounts;

    uint256 public borrowingFactorPercent = 200;

    function viewHourlyBondAmount(address issuer, address holder) public view returns (uint256) {
        HourlyBond storage bond = hourlyBondAccounts[issuer][holder];
        uint256 yieldQuotientFP = bond.yieldQuotientFP;

        uint256 cumulativeYield = viewCumulativeYieldFP(hourlyBondMetadata[issuer].yieldAccumulator, block.timestamp);

        if (yieldQuotientFP > 0) {
            return bond.amount + applyInterest(bond.amount, cumulativeYield, yieldQuotientFP);
        }
        return bond.amount + 0;
    }

    function calcCumulativeYieldFP(YieldAccumulator storage yieldAccumulator, uint256 timeDelta) internal view returns (uint256 accumulatorFP) {
        uint256 secondsDelta = timeDelta % (1 hours);
        accumulatorFP = (yieldAccumulator.accumulatorFP * yieldAccumulator.hourlyYieldFP * secondsDelta) / (FP32 * 1 hours);

        uint256 hoursDelta = timeDelta / (1 hours);
        if (hoursDelta > 0) {
            for (uint256 i = 0; hoursDelta > i; i++) {
                accumulatorFP = (accumulatorFP * yieldAccumulator.hourlyYieldFP) / FP32;
            }
        }
    }

    function viewCumulativeYieldFP(YieldAccumulator storage yA, uint256 timestamp) internal view returns (uint256) {
        uint256 timeDelta = (timestamp - yA.lastUpdated);
        return calcCumulativeYieldFP(yA, timeDelta);
    }
}
