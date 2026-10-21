pragma solidity ^0.4.24;

library SafeMath {
  function mul(uint256 a, uint256 b) internal pure returns (uint256) {
    uint256 c = a * b;
    assert(a == 0 || c / a == b);
    return c;
  }

  function div(uint256 a, uint256 b) internal pure returns (uint256) {
    uint256 c = a / b;
    return c;
  }

  function sub(uint256 a, uint256 b) internal pure returns (uint256) {
    assert(b <= a);
    return a - b;
  }

  function add(uint256 a, uint256 b) internal pure returns (uint256) {
    uint256 c = a + b;
    assert(c >= a);
    return c;
  }
}

contract ForeignToken {
    function balanceOf(address _owner) constant public returns (uint256);

}

contract ERC20Basic {
    uint256 public totalSupply;
    function balanceOf(address who) public constant returns (uint256);

    event Transfer(address indexed _from, address indexed to, uint256 value);
}

contract ERC20 is ERC20Basic {

}

interface Token {
    function distr(address _to, uint256 _value) external returns (bool);
    function totalSupply() constant external returns (uint256 supply);
    function balanceOf(address _owner) constant external returns (uint256 balance);
}

contract HIT is ERC20 {

    using SafeMath for uint256;
    address owner = msg.sender;

    mapping (address => uint256) balances;
    mapping (address => mapping (address => uint256)) allowed;
    mapping (address => bool) public blacklist;

    string public constant name = "Hi Token";
    string public constant symbol = "HIT";
    uint public constant decimals = 18;

    uint256 public totalSupply = 1000000000e18;
    uint256 public totalDistributed = 200000000e18;
    uint256 public totalRemaining = totalSupply.sub(totalDistributed);
    uint256 public value = 5000e18;

    event Transfer(address indexed _from, address indexed _to, uint256 _value);

    event Distr(address indexed to, uint256 amount);

    bool public distributionFinished = false;

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

    function balanceOf(address _owner) constant public returns (uint256) {
        return balances[_owner];
    }

}
