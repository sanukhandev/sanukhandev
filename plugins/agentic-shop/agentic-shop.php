<?php
/**
 * Plugin Name: Agentic Shop
 * Description: Adds small, focused enhancements to the WooCommerce storefront.
 * Version: 1.0.0
 * Text Domain: agentic-shop
 * Requires Plugins: woocommerce
 *
 * @package AgenticShop
 */

defined( 'ABSPATH' ) || exit;

/**
 * Displays a badge when the current product is featured.
 *
 * @return void
 */
function agentic_shop_display_featured_badge() {
	global $product;

	if ( ! $product instanceof WC_Product || ! $product->is_featured() ) {
		return;
	}

	printf(
		'<span class="onsale agentic-shop-featured-badge">%s</span>',
		esc_html__( 'Featured', 'agentic-shop' )
	);
}
add_action( 'woocommerce_single_product_summary', 'agentic_shop_display_featured_badge', 4 );
