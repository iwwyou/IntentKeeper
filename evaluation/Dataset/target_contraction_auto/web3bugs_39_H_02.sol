pragma solidity 0.8.4;

contract Swivel {
  mapping (bytes32 => bool) public cancelled;
  mapping (bytes32 => uint256) public filled;
  mapping (address => uint256) public withdrawals;

  string constant public NAME = 'Swivel Finance';
  string constant public VERSION = '2.0.0';
  uint256 constant public HOLD = 259200;
  bytes32 public immutable domain;
  address public immutable marketPlace;
  address public immutable admin;
  uint16[] public fenominator;

  event _Exit(bytes32 indexed key, bytes32 hash, address indexed maker, bool vault, bool exit, address indexed sender, uint256 amount, uint256 filled);

  function exitVaultFillingVaultInitiate(Hash.Order calldata o, uint256 a, Sig.Components calldata c) internal {
    bytes32 hash = validOrderHash(o, c);

    require(a <= (o.principal - filled[hash]), 'taker amount > available volume');

    filled[hash] += a;

    uint256 premiumFilled = (((a * 1e18) / o.principal) * o.premium) / 1e18;
    uint256 fee = ((premiumFilled * 1e18) / fenominator[3]) / 1e18;

    Erc20 uToken = Erc20(o.underlying);
    uToken.transferFrom(o.maker, msg.sender, premiumFilled - fee);

    uToken.transferFrom(msg.sender, address(this), fee);

    require(MarketPlace(marketPlace).p2pVaultExchange(o.underlying, o.maturity, msg.sender, o.maker, a), 'vault exchange failed');

    emit _Exit(o.key, hash, o.maker, o.vault, o.exit, msg.sender, a, premiumFilled);
  }

  function validOrderHash(Hash.Order calldata o, Sig.Components calldata c) internal view returns (bytes32) {
    bytes32 hash = Hash.order(o);

    require(!cancelled[hash], 'order cancelled');
    require(o.expiry >= block.timestamp, 'order expired');
    require(o.maker == Sig.recover(Hash.message(domain, hash), c), 'invalid signature');

    return hash;
  }

}
