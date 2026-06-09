pragma solidity ^0.8.4;

interface IUserManager {
    function checkIsMember(address account) external view returns (bool);

    function getBorrowerAddresses(address account) external view returns (address[] memory);

    function getStakerAddresses(address account) external view returns (address[] memory);

    function getBorrowerAsset(address account, address borrower)
        external
        view
        returns (
            uint256,
            uint256,
            uint256
        );

    function getStakerAsset(address account, address staker)
        external
        view
        returns (
            uint256,
            uint256,
            uint256
        );

    function getCreditLimit(address account) external view returns (int256);

    function totalStaked() external view returns (uint256);

    function totalFrozen() external view returns (uint256);

    function getFrozenCoinAge(address staker, uint256 pastBlocks) external view returns (uint256);

    function addMember(address account) external;

    function updateTrust(address borrower, uint256 trustAmount) external;

    function registerMember(address newMember) external;

    function cancelVouch(address staker, address account) external;

    function setCreditLimitModel(address newCreditLimitModel) external;

    function getTotalLockedStake(address staker) external view returns (uint256);

    function getTotalFrozenAmount(address staker) external view returns (uint256);

    function updateLockedData(
        address borrower,
        uint256 amount,
        bool isBorrow
    ) external;

    function getStakerBalance(address account) external view returns (uint256);

    function stake(uint256 amount) external;

    function unstake(uint256 amount) external;

    function updateTotalFrozen(address account, bool isOverdue) external;

    function batchUpdateTotalFrozen(address[] calldata account, bool[] calldata isOverdue) external;

    function repayLoanOverdue(
        address account,
        address token,
        uint256 lastRepay
    ) external;
}
