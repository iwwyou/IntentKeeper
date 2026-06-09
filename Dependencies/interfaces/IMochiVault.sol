pragma solidity ^0.8.0;

struct Detail {
    Status status;
    uint256 collateral;
    uint256 debt;
    uint256 debtIndex;
    address referrer;
}

enum Status {
    Invalid,
    Idle,
    Collaterized,
    Active,
    Liquidated
}

interface IMochiVault {
    function liveDebtIndex() external view returns (uint256);

    function details(uint256 _nftId)
        external
        view
        returns (
            Status,
            uint256 collateral,
            uint256 debt,
            uint256 debtIndexe,
            address refferer
        );

    function status(uint256 _nftId) external view returns (Status);

    function asset() external view returns (IERC20);

    function deposits() external view returns (uint256);

    function debts() external view returns (uint256);

    function claimable() external view returns (int256);

    function currentDebt(uint256 _nftId) external view returns (uint256);

    function initialize(address _asset) external;

    function deposit(uint256 _nftId, uint256 _amount) external;

    function withdraw(
        uint256 _nftId,
        uint256 _amount,
        bytes memory _data
    ) external;

    function borrow(
        uint256 _nftId,
        uint256 _amount,
        bytes memory _data
    ) external;

    function repay(uint256 _nftId, uint256 _amount) external;

    function liquidate(
        uint256 _nftId,
        uint256 _collateral,
        uint256 _usdm
    ) external;
}
