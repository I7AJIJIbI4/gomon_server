<?php

class StoreModuleOrderItem {
	/** @var StoreModuleOrder */
	private $order = null;

	/** @var string */
	public $name = "";
	/** @var string */
	public $sku = "";
	/** @var float */
	public $price = 0.0;
	/** @var float */
	public $fullPrice = 0.0;
	/** @var float */
	public $discount = 0.0;
	/** @var int */
	public $quantity = 0;
	/** @var StoreModuleOrderItemCustomField[] */
	public $customFields = array();
	/** @var StoreModuleOrderItemFiles[]  */
	public $files = [];

	protected function __construct(StoreModuleOrder $order) {
		$this->order = $order;
	}

	/**
	 * @param StoreModuleOrder $order
	 * @param Profis\SitePro\controller\StoreDataItem $cartItem
	 * @return StoreModuleOrderItem
	 */
	public static function fromCartItem(StoreModuleOrder $order, $cartItem) {
		$storeItem = StoreData::findItemById($cartItem->id);
		$variant = $storeItem ? StoreData::detectItemVariant($storeItem, $cartItem) : null;
		$name = $variant ? StoreData::buildVariantName($variant, $cartItem->name) : $cartItem->name;

		$item = new self($order);
		$item->name = $name;
		$item->sku = $cartItem->sku;
		$item->fullPrice = $cartItem->fullPrice;
		$item->price = $cartItem->price;
		$item->discount = $cartItem->discount;
		$item->quantity = max(isset($cartItem->quantity) ? intval($cartItem->quantity) : 1, 1);
		if ($item->discount > 0 && $item->discount < 100) {
			$item->fullPrice = round($item->price * 100 / (100 - $item->discount) * 100) / 100;
		} else {
			$item->fullPrice = $item->price;
		}
		$itemType = StoreData::getItemType($cartItem->itemType);
		foreach( $cartItem->customFields as $customField ) {
			$field = StoreData::getItemTypeField($itemType, $customField->fieldId);
			if (!$field) continue;
			$fieldValue = StoreElement::stringifyFieldValue($customField, $field);
			$item->customFields[] = new StoreModuleOrderItemCustomField(tr_($field->name), $fieldValue);
		}
		foreach ( $cartItem->files as $file ) {
			$item->files[] = new StoreModuleOrderItemFiles($file->name, $file->src, $file->extension);
		}
		return $item;
	}

	/**
	 * @param StoreModuleOrder $order
	 * @param stdClass|array $data
	 * @return StoreModuleOrderItem
	 */
	public static function fromJson(StoreModuleOrder $order, $data) {
		if( !is_object($data) )
			$data = (object)$data;
		$item = new self($order);
		$item->name = $data->name;
		$item->sku = $data->sku;
		$item->price = $data->price;
		$item->fullPrice = isset($data->fullPrice) ? $data->fullPrice : 0;
		$item->discount = isset($data->discount) ? $data->discount : 0;
		$item->quantity = $data->quantity;
		if ((!$item->fullPrice || $item->fullPrice == $item->price) && $item->discount > 0 && $item->discount < 100) {
			$item->fullPrice = round($item->price * 100 / (100 - $item->discount) * 100) / 100;
		} else if (!$item->fullPrice) {
			$item->fullPrice = $item->price;
		}
		$item->customFields = array();
		foreach( $data->customFields as $cfData )
			$item->customFields[] = StoreModuleOrderItemCustomField::fromJson($cfData);
		$item->files = array();
		if (isset($data->files) && is_array($data->files)) {
			foreach ($data->files as $file)
				$item->files[] = StoreModuleOrderItemFiles::fromJson($file);
		}
		return $item;
	}

	public function jsonSerialize() {
		$customFields = array();
		foreach( $this->customFields as $field )
			$customFields[] = $field->jsonSerialize();
		$files = array();
		foreach( $this->files as $file ) {
			$files[] = $file->jsonSerialize();
		}
		return array(
			"name" => $this->name,
			"sku" => $this->sku,
			"fullPrice" => $this->fullPrice,
			"price" => $this->price,
			"discount" => $this->discount,
			"quantity" => $this->quantity,
			"customFields" => $customFields,
			"files" => $files,
		);
	}

	public function getFormattedPrice() {
		return StoreData::formatPrice($this->price, $this->order->getPriceOptions(), $this->order->getCurrency());
	}

	public function getFormattedFullPrice() {
		return StoreData::formatPrice(
				$this->fullPrice,
				$this->order->getPriceOptions(),
				$this->order->getCurrency());
	}

	public function __toString() {
		return trim(tr_($this->name))
			.' ('.StoreModule::__('SKU').": ".trim($this->sku).")"
			.' ('.StoreModule::__('Price').": "
				.$this->getFormattedPrice()
				.(($this->discount > 0) ? (' <s>'.$this->getFormattedFullPrice().'</s>') : '')
			.")"
			.' ('.StoreModule::__('Qty').': '.$this->quantity.')';
	}
}