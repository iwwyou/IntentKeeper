pragma solidity ^0.8.0;

contract Governed {
    address public gov;
    address private pendingGov;
    address public emergency_gov;

}

interface IGoverned {
    function gov() external view returns (address);
    function emergency_gov() external view returns (address);
}

abstract contract ExternallyGoverned {
    IGoverned public gov;

}

interface LockeCallee {
    function lockeCall(address initiator, address token, uint256 amount, bytes calldata data) external;
}

contract Stream is LockeERC20, ExternallyGoverned {
    using SafeTransferLib for ERC20;
    struct TokenStream {
        uint256 lastCumulativeRewardPerToken;
        uint256 virtualBalance;
        uint112 rewards;
        uint112 tokens;
        uint32 lastUpdate;
        bool merkleAccess;
    }

    uint32 private immutable startTime;
    uint32 private immutable streamDuration;
    uint32 private immutable depositLockDuration;
    uint32 private immutable rewardLockDuration;

    uint32 private immutable endStream;
    uint32 private immutable endDepositLock;
    uint32 private immutable endRewardLock;

    address public immutable rewardToken;
    address public immutable depositToken;

    uint64 public immutable streamId;

    uint16 private immutable feePercent;
    bool private immutable feeEnabled;

    bool public immutable isSale;

    address public immutable streamCreator;

    uint112 private immutable depositDecimalsOne;

    uint112 private rewardTokenAmount;
    uint112 private depositTokenAmount;

    uint112 private rewardTokenFeeAmount;
    uint112 private depositTokenFlashloanFeeAmount;
    uint8 private unlocked = 1;
    bool private claimedDepositTokens;

    uint256 private cumulativeRewardPerToken;

    uint256 private totalVirtualBalance;

    uint112 public unstreamed;
    uint112 private redeemedDepositTokens;
    uint32 private lastUpdate;

    mapping (address => TokenStream) public tokensNotYetStreamed;

    mapping (address => uint112) public incentives;

    event SoldTokensClaimed(address indexed who, uint256 amount);

    function lockInternal() internal {
        require(unlocked == 1, "re");
        unlocked = 2;
    }
    modifier lock {
        lockInternal();
        _;
        unlocked = 1;
    }

    function creatorClaimSoldTokens(address destination) public lock {
        require(isSale, "!sale");

        require(!claimedDepositTokens, "claimed");
        require(msg.sender == streamCreator, "!creator");
        require(block.timestamp >= endStream, "stream");

        uint112 amount = depositTokenAmount;
        claimedDepositTokens = true;

        ERC20(depositToken).safeTransfer(destination, amount);

        emit SoldTokensClaimed(destination, amount);
    }

}

contract StreamFactory is Governed {

    struct GovernableStreamParams {
        uint32 maxDepositLockDuration;
        uint32 maxRewardLockDuration;
        uint32 maxStreamDuration;
        uint32 minStreamDuration;
    }

    struct GovernableFeeParams {
        uint16 feePercent;
        bool feeEnabled;
    }

    GovernableStreamParams public streamParams;
    GovernableFeeParams public feeParams;
    uint64 public currStreamId;

    uint16 constant MAX_FEE_PERCENT = 500;

}
