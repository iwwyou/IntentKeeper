pragma solidity ^0.8.11;

contract MasterChef is Ownable, ReentrancyGuard {
    using SafeMath for uint;
    using SafeERC20 for IERC20;

    struct UserInfo {
        uint128 amount;
        uint128 rewardDebt;
    }

    struct PoolInfo {
        IERC20 depositToken;
        uint allocPoint;
        uint lastRewardBlock;
        uint accConcurPerShare;
        uint16 depositFeeBP;
    }

    PoolInfo[] public poolInfo;
    mapping(uint => mapping(address => UserInfo)) public userInfo;
    mapping(address => bool) public isDepositor;
    mapping(address => uint256) public pid;
    uint public concurPerBlock = 100000 gwei;
    uint public totalAllocPoint = 0;
    uint public startBlock;
    uint public endBlock;
    IERC20 public concur;

    uint private _concurShareMultiplier = 1e18;
    uint private _perMille = 1000;

    function add(address _token, uint _allocationPoints, uint16 _depositFee, uint _startBlock) public onlyOwner {
        require(_token != address(0), "zero address");
        uint lastRewardBlock = block.number > _startBlock ? block.number : _startBlock;
        totalAllocPoint = totalAllocPoint.add(_allocationPoints);
        require(pid[_token] == 0, "already registered");
        poolInfo.push(PoolInfo({
                depositToken: IERC20(_token), allocPoint: _allocationPoints, lastRewardBlock: lastRewardBlock, accConcurPerShare: 0, depositFeeBP: _depositFee
            }));
        pid[_token] = poolInfo.length - 1;
    }

}
