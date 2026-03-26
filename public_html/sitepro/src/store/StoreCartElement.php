<?php

/**
 * Render store cart element.
 * @property StoreCartElementOptions $options
 */
class StoreCartElement extends StoreBaseElement {
	
	public function __construct($options) {
		parent::__construct($options);
	}
	
	protected function renderCartAction(StoreNavigation $request) {
		$urlAnchor = StoreModule::$storeAnchor ? '#'.StoreModule::$storeAnchor : '';
		$this->renderView($this->viewPath.'/cart-elem.php', array(
			'elementId' => $this->options->id,
			'count' => StoreData::countCartItems(),
			'name' => ($this->options->name ?: ''),
			'icon' => $this->options->icon,
			'iconWidth' => $this->options->iconWidth,
			'iconHeight' => $this->options->iconHeight,
			'iconColor' => $this->options->iconColor,
			'cartUrl' => (is_null($request->defaultStorePageRoute)
					? $request->detailsUrl(null, 'wb_cart')
					: $request->getUri($request->defaultStorePageRoute.'/wb_cart'.$urlAnchor)
				)
		));
	}
	
	/** @param StoreCartElementOptions $options */
	public static function render(StoreNavigation $request, $options) {
		$elem = new StoreCartElement($options);
		$elem->renderCartAction($request);
	}
	
}

/**
 * @property string $id cart element identifier.
 * @property string $name cart element title.
 * @property string $icon cart element icon.
 * @property string|null $iconWidth cart element icon width.
 * @property string|null $iconHeight cart element icon height.
 * @property string|null $iconColor cart element icon color.
 */
class StoreCartElementOptions {}
