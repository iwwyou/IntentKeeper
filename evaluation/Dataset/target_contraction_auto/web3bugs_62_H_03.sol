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

    event RewardsClaimed(address indexed who, uint256 amount);

    function lockInternal() internal {
        require(unlocked == 1, "re");
        unlocked = 2;
    }
    modifier lock {
        lockInternal();
        _;
        unlocked = 1;
    }

    function lastApplicableTime() internal view returns (uint32) {
        return block.timestamp <= endStream ? uint32(block.timestamp) : endStream;
    }

    function rewardPerToken() public view returns (uint256) {
        if (totalVirtualBalance == 0) {
            return cumulativeRewardPerToken;
        } else {
            return cumulativeRewardPerToken + (((uint256(lastApplicableTime()) - lastUpdate) * rewardTokenAmount * depositDecimalsOne/streamDuration) / totalVirtualBalance);
        }
    }

    function earned(TokenStream storage ts, uint256 currCumRewardPerToken) internal view returns (uint112) {
        return uint112(ts.virtualBalance * (currCumRewardPerToken - ts.lastCumulativeRewardPerToken) / depositDecimalsOne) + ts.rewards;
    }

    function claimReward() public lock {
        require(block.timestamp > endRewardLock, "lock");

        TokenStream storage ts = tokensNotYetStreamed[msg.sender];
        cumulativeRewardPerToken = rewardPerToken();

        ts.rewards = earned(ts, cumulativeRewardPerToken);
        ts.lastCumulativeRewardPerToken = cumulativeRewardPerToken;

        lastUpdate = lastApplicableTime();

        uint256 rewardAmt = ts.rewards;
        ts.rewards = 0;

        require(rewardAmt > 0, "amt");

        ERC20(rewardToken).safeTransfer(msg.sender, rewardAmt);

        emit RewardsClaimed(msg.sender, rewardAmt);
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
