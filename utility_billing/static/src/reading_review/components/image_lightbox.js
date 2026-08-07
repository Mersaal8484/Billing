/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";

export class ReadingImageLightbox extends Component {
    setup() {
        this.state = useState({
            zoom: 1.0,
            rotation: 0,
            variant: "review",
        });

        this.handleKeyDown = this.handleKeyDown.bind(this);

        onMounted(() => {
            window.addEventListener("keydown", this.handleKeyDown);
        });

        onWillUnmount(() => {
            window.removeEventListener("keydown", this.handleKeyDown);
        });
    }

    handleKeyDown(ev) {
        if (ev.target.tagName === "INPUT" || ev.target.tagName === "TEXTAREA" || ev.target.tagName === "SELECT") {
            return;
        }

        if (ev.key === "Escape") {
            this.props.onClose();
        } else if (ev.key === "ArrowLeft") {
            this.props.onNext();
        } else if (ev.key === "ArrowRight") {
            this.props.onPrevious();
        } else if (ev.key === "+" || ev.key === "=") {
            this.zoomIn();
        } else if (ev.key === "-") {
            this.zoomOut();
        } else if (ev.key === "a" || ev.key === "A") {
            this.props.onApprove(this.props.reading);
        } else if (ev.key === "r" || ev.key === "R") {
            this.props.onReject(this.props.reading);
        }
    }

    zoomIn() {
        this.state.zoom = Math.min(this.state.zoom + 0.25, 3.5);
    }

    zoomOut() {
        this.state.zoom = Math.max(this.state.zoom - 0.25, 0.5);
    }

    rotateLeft() {
        this.state.rotation = (this.state.rotation - 90) % 360;
    }

    rotateRight() {
        this.state.rotation = (this.state.rotation + 90) % 360;
    }

    resetTransform() {
        this.state.zoom = 1.0;
        this.state.rotation = 0;
    }

    setVariant(varName) {
        this.state.variant = varName;
        this.resetTransform();
    }

    getImageUrl() {
        const r = this.props.reading;
        if (!r) return '';
        if (this.state.variant === 'original') {
            return r.original_url || r.review_url || r.thumbnail_url || '';
        } else if (this.state.variant === 'thumbnail') {
            return r.thumbnail_url || r.review_url || '';
        }
        return r.review_url || r.thumbnail_url || '';
    }
}

ReadingImageLightbox.template = "utility_billing.ReadingImageLightbox";
ReadingImageLightbox.props = {
    reading: Object,
    onClose: Function,
    onNext: Function,
    onPrevious: Function,
    onApprove: Function,
    onReject: Function,
};
