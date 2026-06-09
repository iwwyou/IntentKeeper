pragma solidity ^0.8.0;

contract Governed {
    address public gov;
    address private pendingGov;
    address public emergency_gov;

    event NewGov(address indexed oldGov, address indexed newGov);
    event NewPendingGov(address indexed oldPendingGov, address indexed newPendingGov);

    modifier governed {
        require(msg.sender == gov, "!gov");
        _;
    }

    modifier emergency_governed {
        require(msg.sender == gov || msg.sender == emergency_gov, "!egov");
        _;
    }

    function governorship() public view returns (address, address, address) {
        return (gov, emergency_gov, pendingGov);
    }

    function setPendingGov(address newPendingGov) governed public {
        address old = pendingGov;
        pendingGov = newPendingGov;
        emit NewPendingGov(old, newPendingGov);
    }

    function acceptGov() public {
        require(pendingGov == msg.sender, "!pending");
        address old = gov;
        gov = pendingGov;
        emit NewGov(old, pendingGov);
    }

    function setEmergencyGov(address who) public governed {
        emergency_gov = who;
    }

    function __abdicate() governed public {
        address old = gov;
        gov = address(0);
        emit NewGov(old, address(0));
    }
}

interface IGoverned {
    function gov() external view returns (address);
    function emergency_gov() external view returns (address);
}

abstract contract ExternallyGoverned {
    IGoverned public gov;

    modifier externallyGoverned {
        require(msg.sender == gov.gov(), "!gov");
        _;
    }

    modifier externallyEmergencyGoverned {
        require(msg.sender == gov.gov() || msg.sender == gov.emergency_gov(), "!e_gov");
        _;
    }
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

    function lastApplicableTime() internal view returns (uint32) {
        return block.timestamp <= endStream ? uint32(block.timestamp) : endStream;
    }

    function rewardPerToken() public view returns (uint256) {
        if (totalVirtualBalance == 0) {
            return cumulativeRewardPerToken;
        } else {
            return cumulativeRewardPerToken + (
                ((uint256(lastApplicableTime()) - lastUpdate) * rewardTokenAmount * depositDecimalsOne/streamDuration)
                / totalVirtualBalance
            );
        }
    }

    function earned(TokenStream storage ts, uint256 currCumRewardPerToken) internal view returns (uint112) {
        return uint112(ts.virtualBalance * (currCumRewardPerToken - ts.lastCumulativeRewardPerToken) / depositDecimalsOne) + ts.rewards;
    }

    function updateStreamInternal(address who) internal {
        require(block.timestamp < endStream , "!stream");
        TokenStream storage ts = tokensNotYetStreamed[msg.sender];

        if (block.timestamp >= startTime) {
            if (ts.lastUpdate == 0) {
                ts.lastUpdate = uint32(block.timestamp);
            }
            if (lastUpdate == 0) {
                lastUpdate = uint32(block.timestamp);
            }

            cumulativeRewardPerToken = rewardPerToken();

            ts.rewards = earned(ts, cumulativeRewardPerToken);
            ts.lastCumulativeRewardPerToken = cumulativeRewardPerToken;

            uint32 acctTimeDelta = uint32(block.timestamp) - ts.lastUpdate;
            if (acctTimeDelta > 0 && ts.tokens > 0) {
                ts.tokens -= uint112(acctTimeDelta * ts.tokens / (endStream - ts.lastUpdate));
                ts.lastUpdate = uint32(block.timestamp);
            }

            uint32 tdelta = uint32(block.timestamp - lastUpdate);
            if (tdelta > 0 && unstreamed > 0) {
                uint256 globalStreamingSpeedPerSecond = (uint256(unstreamed) * 10**6)/ (endStream - lastUpdate);
                unstreamed -= uint112((uint256(tdelta) * globalStreamingSpeedPerSecond) / 10**6);
            }
            lastUpdate = uint32(block.timestamp);
        } else {
            if (ts.lastUpdate == 0) {
                ts.lastUpdate = startTime;
            }
            if (lastUpdate == 0) {
                lastUpdate = startTime;
            }
        }
    }
}
