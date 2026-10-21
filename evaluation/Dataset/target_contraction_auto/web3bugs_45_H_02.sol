pragma solidity ^0.8.4;

contract CreditLimitByMedian is Ownable, ICreditLimitModel {
    using Math for uint256;

    bool public constant override isCreditLimitModel = true;
    uint256 public override effectiveNumber;

    function getLockedAmount(LockedInfo[] memory _array, address account, uint256 amount, bool isIncrease) public pure override returns (uint256) {
        if (_array.length == 0) {
            return 0;
        }

        uint256 newLockedAmount;
        if (isIncrease) {
            for (uint256 i = 0; i < _array.length; i++) {
                uint256 remainingVouchingAmount;
                if (_array[i].vouchingAmount > _array[i].lockedAmount) {
                    remainingVouchingAmount = _array[i].vouchingAmount - _array[i].lockedAmount;
                } else {
                    remainingVouchingAmount = 0;
                }

                if (remainingVouchingAmount > _array[i].availableStakingAmount) {
                    if (_array[i].availableStakingAmount > amount) {
                        newLockedAmount = _array[i].lockedAmount + amount;
                    } else {
                        newLockedAmount = _array[i].lockedAmount + _array[i].availableStakingAmount;
                    }
                } else {
                    if (remainingVouchingAmount > amount) {
                        newLockedAmount = _array[i].lockedAmount + amount;
                    } else {
                        newLockedAmount = _array[i].lockedAmount + remainingVouchingAmount;
                    }
                }

                if (account == _array[i].staker) {
                    return newLockedAmount;
                }
            }
        } else {
            for (uint256 i = 0; i < _array.length; i++) {
                if (_array[i].lockedAmount > amount) {
                    newLockedAmount = _array[i].lockedAmount - 1;
                } else {
                    newLockedAmount = 0;
                }

                if (account == _array[i].staker) {
                    return newLockedAmount;
                }
            }
        }

        return 0;
    }

}
