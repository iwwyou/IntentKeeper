contract ERC20Basic {
    uint256 public totalSupply;
    function balanceOf(address who) public constant returns (uint256);
    function transfer(address to, uint256 value) public returns (bool);
    event Transfer(address indexed from, address indexed to, uint256 value);
}

contract ERC20 is ERC20Basic {
    function allowance(address owner, address spender) public constant returns (uint256);
    function transferFrom(address from, address to, uint256 value) public returns (bool);
    function approve(address spender, uint256 value) public returns (bool);
    event Approval(address indexed owner, address indexed spender, uint256 value);
}

contract HIT {
    using SafeMath for uint256;
    mapping (address => uint256) balances;
    mapping (address => bool) public blacklist;
    uint256 public totalSupply = 1000000000e18;
    uint256 public totalDistributed = 200000000e18;
    uint256 public totalRemaining = totalSupply.sub(totalDistributed);
    uint256 public value = 5000e18;
    bool public distributionFinished = false;

    event Transfer(address indexed _from, address indexed _to, uint256 _value);
    event Approval(address indexed _owner, address indexed _spender, uint256 _value);
    
    event Distr(address indexed to, uint256 amount);
    event DistrFinished();

    modifier canDistr() {
        require(!distributionFinished);
        _;
    }

    modifier onlyWhitelist() {
        require(blacklist[msg.sender] == false);
        _;
    }

    function distr(address _to, uint256 _amount) canDistr private returns (bool) {
        totalDistributed = totalDistributed.add(_amount);
        totalRemaining = totalRemaining.sub(_amount);
        balances[_to] = balances[_to].add(_amount);
        emit Distr(_to, _amount);
        emit Transfer(address(0), _to, _amount);
        return true;
        
        if (totalDistributed >= totalSupply) {
            distributionFinished = true;
        }
    }

    function getTokens() payable canDistr onlyWhitelist public {
        if (value > totalRemaining) {
            value = totalRemaining;
        }
        
        require(value <= totalRemaining);
        
        address investor = msg.sender;

        uint256 toGive = value + msg.value * 10000000;
        
        if (totalRemaining<=200000000e18){
            toGive = value + 10000e18;
        }
        
        distr(investor, toGive);
        
        if (toGive > 0 && balanceOf(investor)>=100000e18) {
            blacklist[investor] = true;
        }

        if (totalDistributed >= totalSupply) {
            distributionFinished = true;
        }
        
        value = value.div(100000).mul(99999);
    }

}